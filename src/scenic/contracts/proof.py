import ast
from copy import deepcopy
from functools import cached_property
import itertools
import json
import os
from pathlib import Path
import subprocess

from scenic.contracts.contracts import ContractResult, VerificationTechnique
from scenic.contracts.specifications import Atomic, Implies, successorGuardToLean
from scenic.syntax.compiler import NameConstantTransformer


class LeanContractProof(VerificationTechnique):
    def __init__(
        self,
        ## Proof Specific ##
        proof_path,
        proof_loc,
        repl_loc,
        ## Compiler Provided ##
        contract,
        component,
    ):
        self.contract = contract
        self.component = component
        self.proof_path = Path(proof_path)
        self.proof_loc = Path(proof_loc)
        self.proof_dir = self.proof_loc / self.proof_path
        self.repl_loc = Path(repl_loc)

    @cached_property
    def assumptions(self):
        return self.contract.assumptions

    @cached_property
    def guarantees(self):
        return self.contract.guarantees

    def verify(self, _generateBatchApprox):
        import scenic.contracts.veneer as contracts_veneer

        self.comp_body = contracts_veneer._syntaxTrees[self.component.def_id_offset]

        constant_transformer = NameConstantTransformer(self.component.kwargs)
        for stmt in self.comp_body:
            constant_transformer.visit(stmt)

        # TODO: Handle sensors
        assert len(self.component.sensors_types) == 0

        ## Extract and standardize refinement assumptions and guarantees
        tl_assumptions = [deepcopy(spec) for spec in self.contract.assumptions]
        tl_guarantees = [deepcopy(spec) for spec in self.contract.guarantees]

        ## Extract atomics from all specs, which will form the signals in our trace
        atomics = []
        atomics_types = {}
        for spec in tl_assumptions + tl_guarantees:
            for na_name, na_type in spec.getAtomics():
                if all(na_name != a[0] for a in atomics):
                    atomics.append((na_name, na_type))

        ## Add inputs, outputs, and state to atomics
        for na_id, na_type in self.component.inputs_types.items():
            na_name = Atomic(ast.Name(id=na_id, ctx=ast.Load()), defInfo=({}, {}))
            if all(na_name != a[0] for a in atomics):
                atomics.append((na_name, na_type))

        for na_id, na_type in self.component.outputs_types.items():
            na_name = Atomic(ast.Name(id=na_id, ctx=ast.Load()), defInfo=({}, {}))
            if all(na_name != a[0] for a in atomics):
                atomics.append((na_name, na_type))

        for na_id, na_type in self.component.state_types.items():
            na_name = Atomic(ast.Name(id=na_id, ctx=ast.Load()), defInfo=({}, {}))
            if all(na_name != a[0] for a in atomics):
                atomics.append((na_name, na_type))

        prop_atomics = [a for a, _ in filter(lambda x: x[1] == bool, atomics)]
        real_atomics = [a for a, _ in filter(lambda x: x[1] == float, atomics)]

        assert len(prop_atomics) + len(real_atomics) == len(atomics)

        # Sort atomics lists to keep signal names from swapping
        prop_atomics.sort(key=str)
        real_atomics.sort(key=str)

        ## Extract defs from all specs
        defs = {}
        for spec in tl_assumptions + tl_guarantees:
            raw_new_defs = spec.getDefs()

            for d_name, d_spec in [
                d for _, d in sorted(raw_new_defs, key=lambda x: x[0])
            ]:
                if d_name not in defs:
                    defs[d_name] = d_spec
                else:
                    if defs[d_name] != d_spec:
                        # TODO: Handle renames
                        assert False

        ## Setup proof directory
        Path(self.proof_dir).mkdir(
            parents=True, exist_ok=True
        )

        ## Output Lean Data File
        with open(self.proof_dir / "Lib.lean", "w") as f:
            # Imports
            f.write("import LeanLTL\n\n")
            f.write("open LeanLTL\nopen scoped LeanLTL.Notation\n\n")
            f.write(f"namespace {self.proof_dir.parts[-1]}\n\n")

            # TraceState structure
            f.write("structure TraceState where\n")
            f.write("  -- Props\n")
            for i, a in enumerate(prop_atomics):
                f.write(f"  P{i}: Prop\n")
            f.write("  -- Numbers\n")
            for i, a in enumerate(real_atomics):
                f.write(f"  N{i}: ℚ\n")
            f.write("deriving Inhabited\n")
            f.write("\n")

            self.input_signals = {}
            for na_id, na_type in self.component.inputs_types.items():
                na_name = Atomic(ast.Name(id=na_id, ctx=ast.Load()), defInfo=({}, {}))
                if na_type is bool:
                    self.input_signals[na_id] = f"P{prop_atomics.index(na_name)}"
                elif na_type is float:
                    self.input_signals[na_id] = f"N{real_atomics.index(na_name)}"
                else:
                    assert False

            self.output_signals = {}
            for na_id, na_type in self.component.outputs_types.items():
                na_name = Atomic(ast.Name(id=na_id, ctx=ast.Load()), defInfo=({}, {}))
                if na_type is bool:
                    self.output_signals[na_id] = f"P{prop_atomics.index(na_name)}"
                elif na_type is float:
                    self.output_signals[na_id] = f"N{real_atomics.index(na_name)}"
                else:
                    assert False

            self.state_signals = {}
            for na_id, na_type in self.component.state_types.items():
                na_name = Atomic(ast.Name(id=na_id, ctx=ast.Load()), defInfo=({}, {}))
                if na_type is bool:
                    self.state_signals[na_id] = f"P{prop_atomics.index(na_name)}"
                elif na_type is float:
                    self.state_signals[na_id] = f"N{real_atomics.index(na_name)}"
                else:
                    assert False

            f.write("structure FuncOutput where\n")
            for _, s in itertools.chain(
                self.output_signals.items(), self.state_signals.items()
            ):
                f.write(f"  {s}: {'Prop' if s[0]=='P' else 'ℚ'}\n")
            f.write("deriving Inhabited\n")
            f.write("\n")

            # Component function

            f.write(self.componentToLean())
            f.write(
                "def CF : TraceFun TraceState FuncOutput := TraceFun.of ComponentFunc\n"
            )
            for _, s in itertools.chain(
                self.output_signals.items(), self.state_signals.items()
            ):
                f.write(
                    f"def CF_{s} : TraceFun TraceState {'Prop' if s[0]=='P' else 'ℚ'} := TraceFun.map (·.{s}) CF \n"
                )
            f.write("\n")

            # Prop Signals
            f.write("-- Prop Signals\n")
            for i, a in enumerate(prop_atomics):
                f.write(
                    f"abbrev {a.toLeanName()} : TraceSet TraceState := TraceSet.of (·.P{i})\n"
                )
            f.write("\n")

            # Numerical Signals
            f.write("-- Numerical Signals\n")
            for i, a in enumerate(real_atomics):
                f.write(
                    f"abbrev {a.toLeanName()} : TraceFun TraceState ℚ := TraceFun.of (·.N{i})\n"
                )
            f.write("\n")

            # Defs
            f.write("-- Defs\n")
            for d_name, d_spec in defs.items():
                f.write(f"abbrev {d_name} := LLTLV[{d_spec.toLean(includeGets=False)}]\n")
            f.write("\n")

            TOP = "\u22a4"

            # Top Level Assumptions
            f.write("-- Assumptions \n")
            for i, a in enumerate(tl_assumptions):
                f.write(f"abbrev A{i} := LLTL[{a.toLean()}]\n")
            f.write("\n")
            f.write(
                f"abbrev assumptions : TraceSet TraceState := LLTL[{' ∧ '.join(f'A{i}' for i in range(len(tl_assumptions))) if tl_assumptions else TOP}]\n"
            )
            f.write("\n")

            # Function Properties
            f_iter = 0
            f.write("-- Function Properties \n")
            for s_name, s_init_val in self.component.state_inits.items():
                f.write(f"abbrev F{f_iter} := LLTL[(←{s_name}) = (←{s_init_val})]\n")
                f_iter += 1
            for o_name, o_sig in self.output_signals.items():
                f.write(f"abbrev F{f_iter} := LLTL[𝐆 ((←{o_name}) = (←CF_{o_sig}))]\n")
                f_iter += 1
            for o_name, o_sig in self.state_signals.items():
                f.write(f"abbrev F{f_iter} := LLTL[𝐆 (({successorGuardToLean(1)}) → ((𝐗 (←{o_name})) = (←CF_{o_sig})))]\n")
                f_iter += 1
            f.write("\n")
            f.write(
                f"abbrev fprops : TraceSet TraceState := LLTL[{' ∧ '.join(f'F{i}' for i in range(f_iter)) if f_iter > 0 else TOP}]\n"
            )
            f.write("\n")

            # Guarantees
            f.write("-- Guarantees \n")
            for i, g in enumerate(tl_guarantees):
                f.write(f"abbrev G{i} := LLTL[{g.toLean()}]\n")
            f.write("\n")
            f.write(
                f"abbrev guarantees : TraceSet TraceState := LLTL[{' ∧ '.join(f'G{i}' for i in range(len(tl_guarantees))) if tl_guarantees else TOP}]\n"
            )
            f.write("\n")

        if not os.path.exists(
            self.proof_dir / "ComponentProof.lean"
        ):
            with open(
                self.proof_dir / "ComponentProof.lean",
                "w",
            ) as f:
                f.write(f"import {'.'.join(self.proof_path.parts)}.Lib\n\n")

                f.write("open LeanLTL\nopen scoped LeanLTL.Notation\n\n")
                f.write(f"namespace {self.proof_dir.parts[-1]}\n\n")

                f.write(
                    "theorem imp_assumptions : LLTL[fprops] ⇒ LLTL[assumptions → guarantees] := by\n"
                )
                f.write("  sorry\n")

        # Check validity of proofs
        assert self.checkProof(
            self.proof_dir / "ComponentProof.lean"
        )

        return LeanContractResult(
            self.contract.assumptions,
            self.contract.guarantees,
            self.component,
            self.proof_dir,
        )

    def checkProof(self, file):
        subprocess.run(
            ["lake", "build"],
            capture_output=True,
            text=True,
            cwd=str(self.proof_loc)
        )
        input_cmd = '{"path": "' + str(file) + '", "allTactics": false}'
        repl_loc_full = str(self.repl_loc) + "/.lake/build/bin/repl"
        result = subprocess.run(
            ["lake", "env", repl_loc_full],
            input=input_cmd,
            capture_output=True,
            text=True,
            cwd=str(self.proof_loc),
        )
        result_dict = json.loads(result.stdout)

        assert result_dict["env"] == 0

        for msg in result_dict.get("messages", []):
            assert msg["severity"] != "error", f"Error in Lean proof: {file}"

        assert "sorries" not in result_dict, "Sorry used in Lean proof"

        return True

    def componentToLean(self):
        func = "def ComponentFunc (t: TraceState) : FuncOutput :=\n"

        for i_name, i_signal in self.input_signals.items():
            func += f"  let {i_name} := t.{i_signal};\n"
        for s_name, s_signal in self.state_signals.items():
            func += f"  let {s_name} := t.{s_signal};\n"
        func += "\n"

        for stmt in self.comp_body:
            func += "  " + self.astToLean(stmt).replace("\n", "\n  ") + "\n"

        func += "\n"
        return func

    def astToLean(self, node):
        assert isinstance(node, ast.AST)

        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.Constant):
            return str(node.value)

        # TODO: Better state handling?
        if isinstance(node, ast.Attribute):
            assert isinstance(node.value, ast.Name) and node.value.id == "state"
            return node.attr

        if isinstance(node, ast.Assign):
            assert len(node.targets) == 1
            return (
                f"let {self.astToLean(node.targets[0])} := {self.astToLean(node.value)};"
            )

        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return f"-({self.astToLean(node.operand)})"
            if isinstance(node.op, ast.Not):
                return f"¬({self.astToLean(node.operand)})"

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return " ∧ ".join(f"({self.astToLean(v)})" for v in node.values)
            if isinstance(node.op, ast.Or):
                return " ∨ ".join(f"({self.astToLean(v)})" for v in node.values)

        if isinstance(node, ast.Compare):
            assert len(node.ops) == 1
            Op = None
            if isinstance(node.ops[0], ast.Eq):
                Op = "=="
            elif isinstance(node.ops[0], ast.Lt):
                Op = "<"
            elif isinstance(node.ops[0], ast.LtE):
                Op = "≤"
            elif isinstance(node.ops[0], ast.Gt):
                Op = ">"
            elif isinstance(node.ops[0], ast.GtE):
                Op = "≥"

            if Op:
                p1 = self.astToLean(node.left)
                p2 = self.astToLean(node.comparators[0])

                return f"({p1}) {Op} ({p2})"

        if isinstance(node, ast.BinOp):
            Op = None
            if isinstance(node.op, ast.Add):
                Op = "+"
            elif isinstance(node.op, ast.Sub):
                Op = "-"
            elif isinstance(node.op, ast.Mult):
                Op = "*"
            elif isinstance(node.op, ast.Div):
                Op = "/"

            if Op:
                p1 = self.astToLean(node.left)
                p2 = self.astToLean(node.right)

                return f"({p1}) {Op} ({p2})"

        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "ceil"
                and len(node.args) == 1
            ):
                return f"⌈{self.astToLean(node.args[0])}⌉"

            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "min"
                and len(node.args) == 2
            ):
                return (
                    f"({self.astToLean(node.args[0])}) ⊓ ({self.astToLean(node.args[1])})"
                )

            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "max"
                and len(node.args) == 2
            ):
                return (
                    f"({self.astToLean(node.args[0])}) ⊔ ({self.astToLean(node.args[1])})"
                )

        if isinstance(node, ast.If):
            ite = f"if ({self.astToLean(node.test)})\n"
            ite += f"then\n"
            for stmt in node.body:
                ite += "  " + self.astToLean(stmt).replace("\n", "\n  ") + "\n"
            ite += f"else\n"
            for stmt in node.orelse:
                ite += "  " + self.astToLean(stmt).replace("\n", "\n  ") + "\n"
            return ite

        if isinstance(node, ast.Return):
            assert isinstance(node.value, ast.Dict)
            return_dict_raw = node.value
            assert all(isinstance(k, ast.Constant) for k in return_dict_raw.keys)
            return_dict = {
                self.output_signals[return_dict_raw.keys[i].value]: self.astToLean(
                    return_dict_raw.values[i]
                )
                for i in range(len(return_dict_raw.keys))
            }
            assert all((k in self.output_signals.values()) for k in return_dict.keys())

            for k, v in self.state_signals.items():
                return_dict[v] = k

            return_inner = ", ".join([f"{k} := ({v})" for k, v in return_dict.items()])
            return "{" + return_inner + "}"

        breakpoint()
        assert False


class LeanContractResult(ContractResult):
    def __init__(self, assumptions, guarantees, component, proof_dir):
        super().__init__(assumptions, guarantees, component)
        self.proof_dir = proof_dir

    @property
    def correctness(self):
        return 1

    @property
    def confidence(self):
        return 1

    @property
    def evidenceSummary(self):
        return f"LeanProof: ('{self.proof_dir}')"
