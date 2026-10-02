import ast
from copy import copy, deepcopy
from functools import cached_property, reduce
import itertools
import math
from math import prod

import pacti
from pacti.contracts import PropositionalIoContract

from scenic.contracts.components import ActionComponent, BaseComponent, ComposeComponent
from scenic.contracts.contracts import ContractResult, VerificationTechnique
import scenic.contracts.specifications as specs
from scenic.contracts.assumption import Assumption
from scenic.contracts.proof import LeanContractProof
from scenic.contracts.testing import Testing, SimulationTestingContractResult, SimulationTestData, TestResult
from scenic.core.distributions import Options, Range
from scenic.syntax.compiler import NameFinder, NameSwapTransformer


def nodeNames(node):
    nf = NameFinder()
    nf.visit(node)
    return nf.names


class Composition(VerificationTechnique):
    def __init__(
        self,
        ## Compiler Provided ##
        component,
        sub_stmts,
        environment,
    ):
        ## Initialization ##
        # Store parameters
        self.component = component
        self.sub_stmts = sub_stmts

        # Ensure all sub statements are of a valid form
        for stmt in self.sub_stmts:
            assert isinstance(stmt, VerificationTechnique)

        # Extract subcomponents and connections if applicable
        subcomponents = (
            component.subcomponents if isinstance(component, ComposeComponent) else {}
        )
        connections = (
            component.connections if isinstance(component, ComposeComponent) else []
        )

        # Check that all sub-statements are applied to this component
        # or one of it's direct sub-components.
        for stmt in self.sub_stmts:
            assert stmt.component is component or stmt.component in subcomponents.values()

        ## Composition checks ##
        import scenic.contracts.veneer as contracts_veneer

        # Compute general port-variable mapping
        # Encoding map is a dictionary mapping tuples (port_name, subcomponent_name)
        # to a temporary variable. Top level ports have None as subcomponent name.
        self.encoding_map = {}
        self.var_num = 0

        # Assign variables to all connections
        for source, dest in connections:
            # Check if we already have a temporary variable name and if not
            # come up with a new intermediate variable name.
            temp_var_name = (
                self.encoding_map[source]
                if source in self.encoding_map
                else self.tempVarName()
            )

            # Map both variables to the new name
            self.encoding_map[source] = temp_var_name
            self.encoding_map[dest] = temp_var_name

        # Assign any remaining subcomponent port variables to temp names
        for sc_name, sc_obj in subcomponents.items():
            ports = list(sc_obj.inputs_types.keys()) + list(sc_obj.outputs_types.keys())

            for port in ports:
                key = (port, sc_name)

                if key not in self.encoding_map:
                    self.encoding_map[key] = self.tempVarName()

        # Assign any remaining top level port variables to temp names
        tl_ports = list(self.component.inputs_types.keys()) + list(
            self.component.outputs_types.keys()
        )
        for port in tl_ports:
            key = (port, None)

            if key not in self.encoding_map:
                self.encoding_map[key] = self.tempVarName()

        # Compute which temporary variables are internal/external.
        input_temp_vars = {
            var
            for key, var in self.encoding_map.items()
            if key[1] is None and key[0] in self.component.inputs_types
        }
        output_temp_vars = {
            var
            for key, var in self.encoding_map.items()
            if key[1] is None and key[0] in self.component.outputs_types
        }
        internal_temp_vars = set(self.encoding_map.values()) - (
            input_temp_vars | output_temp_vars
        )

        # Compute encoding transformer for each subcomponent and the top level component
        # The encoding transformer should encode all port variables to the appropriate
        # temp variable.
        self.encoding_transformers = {}

        # Subcomponents
        for subcomponent in subcomponents:
            name_map = {}

            for source_info, target_name in self.encoding_map.items():
                if source_info[1] == subcomponent:
                    name_map[source_info[0]] = target_name

            self.encoding_transformers[
                self.component.subcomponents[subcomponent]
            ] = NameSwapTransformer(name_map)

        # Top level component
        name_map = {}
        for source_info, target_name in self.encoding_map.items():
            if source_info[1] == None:
                name_map[source_info[0]] = target_name

        self.encoding_transformers[self.component] = NameSwapTransformer(name_map)

        # Compute decoding transformer for assumptions and guarantees
        # We need two decoding transformers because temp variables can get mapped to different
        # final variables depending on whether or not they're in an assumption or guarantee
        # (specifically in the case where a variable is passed through a component unchanged).
        assumption_decoding_map = {}
        for port in self.component.inputs_types.keys():
            assumption_decoding_map[self.encoding_map[((port, None))]] = port
        assumption_decoding_transformer = NameSwapTransformer(assumption_decoding_map)

        guarantee_decoding_map = {}
        for port in itertools.chain(
            self.component.outputs_types.keys(), self.component.inputs_types.keys()
        ):
            guarantee_decoding_map[self.encoding_map[((port, None))]] = port
        guarantee_decoding_transformer = NameSwapTransformer(guarantee_decoding_map)

        # Initialize pactiAtomicsDict
        pactiAtomicsDict = {}

        # Convert all sub_stmts to PACTI contracts and order/cluster according to sub-component
        stmt_groups = [[] for _ in range(len(self.sub_stmts))]
        stmt_group_loc = {stmt: pos for pos, stmt in enumerate(self.sub_stmts)}

        for sub_stmt in self.sub_stmts:
            encoding_transformer = self.encoding_transformers[sub_stmt.component]

            ## Copy and encode assumptions and guarantees ##
            assumptions = [deepcopy(spec) for spec in sub_stmt.assumptions]
            guarantees = [deepcopy(spec) for spec in sub_stmt.guarantees]

            for spec in assumptions + guarantees:
                spec.applyAtomicTransformer(encoding_transformer)

            # TEMP: Separate non-global assumptions, to be added in at the end
            # TODO: Remove this when PACTI adds support
            non_g_assumptions = [a for a in assumptions if not isinstance(a, specs.Always)]
            g_assumptions = [a for a in assumptions if isinstance(a, specs.Always)]

            # Convert all assumptions and guarantees to PACTI-compatible strings
            pstring_assumptions = [a.toPACTIStr(pactiAtomicsDict) for a in g_assumptions]
            pstring_guarantees = [g.toPACTIStr(pactiAtomicsDict) for g in guarantees]

            # Encode IO variables, create PACTI contract, and store it in the appropriate group
            encoded_input_vars = [
                encoding_transformer.name_map[i]
                for i in sub_stmt.component.inputs_types.keys()
            ] + ["GLOBALS"]
            encoded_output_vars = [
                encoding_transformer.name_map[o]
                for o in sub_stmt.component.outputs_types.keys()
            ]

            pacti_contract = PropositionalIoContract.from_strings(
                input_vars=encoded_input_vars,
                output_vars=encoded_output_vars,
                assumptions=pstring_assumptions,
                guarantees=pstring_guarantees,
            )

            stmt_groups[stmt_group_loc[sub_stmt]].append(pacti_contract)

        # Merge all groups, then compose in order.
        # merged_contracts = [
        #     reduce(lambda x, y: x.merge(y), group) for group in stmt_groups
        # ]
        assert [len(group) == 1 for group in stmt_groups]
        stmt_groups = [g[0] for g in stmt_groups]
        composed_contract = reduce(lambda x, y: x.compose(y), stmt_groups)

        # Extract Scenic contracts from resulting Pacti contract
        tl_assumptions = []
        tl_guarantees = []

        idSpecNodeDict = {v:k for k,v in pactiAtomicsDict.items()}

        for term in composed_contract.a.terms:
            tl_assumptions.append(specs.SpecNode.pactiTermToSpec(term, idSpecNodeDict))

        for term in composed_contract.g.terms:
            tl_guarantees.append(specs.SpecNode.pactiTermToSpec(term, idSpecNodeDict))

        """
        #### START TODO: REPLACE THIS BLOCK WITH PACTI

        ## Split out purely external assumptions.
        # External assumptions can be moved to the top level contract
        internal_assumptions = []

        for assumption in assumptions:
            names = assumption.getAtomicNames()
            temp_var_names = self.extractTempVars(names)
            if temp_var_names <= input_temp_vars:
                tl_assumptions.append(assumption)
            else:
                internal_assumptions.append(assumption)

        ## Attempt to discharge all internal assumptions using accumulated top-level
        ## assumptions and guarantees.
        for assumption in internal_assumptions:
            # TACTIC 1: Discharge if we already have this assumption in our accumulated
            # assumptions and guarantees.
            if any(assumption == spec for spec in tl_assumptions + tl_guarantees):
                continue

            # We couldn't prove this assumption :(
            ## DEBUG ##
            print("Assumptions:")
            for a in tl_assumptions:
                print(f"    {a}")

            print("Guarantees:")
            for g in tl_guarantees:
                print(f"    {g}")
            assert False
            breakpoint()

        ## Add guarantees to accumulated top-level guarantees
        tl_guarantees += guarantees

        ## Simplify assumptions and guarantees, removing duplicates
        new_tl_assumptions = []
        for spec in tl_assumptions:
            if not any(spec == e_spec for e_spec in new_tl_assumptions):
                new_tl_assumptions.append(spec)
        tl_assumptions = new_tl_assumptions

        new_tl_guarantees = []
        for spec in tl_guarantees:
            if not any(spec == e_spec for e_spec in new_tl_guarantees) and not any(
                spec == e_spec for e_spec in new_tl_assumptions
            ):
                new_tl_guarantees.append(spec)
        tl_guarantees = new_tl_guarantees

        #### END TODO: REPLACE THIS BLOCK WITH PACTI
        """

        ## Decode top level assumptions and guarantees ##
        # If any assumptions are still using internal temporary variable names after decoding, then
        # they are internal assumptions which are are not being satisfied, and this is not a valid
        # IO contract and we should raise an assertion, as PACTI should handle this.
        # If any guarantees are still using internal temporary variable names after decoding, then
        # they're internal guarantees which aren't relevant to our composition and we should raise
        # an assertion, as PACTI should handle this.
        for spec in tl_assumptions:
            spec.applyAtomicTransformer(assumption_decoding_transformer)
        for spec in tl_guarantees:
            spec.applyAtomicTransformer(guarantee_decoding_transformer)

        for spec in tl_assumptions + tl_guarantees:
            assert len(self.extractTempVars(spec.getAtomicNames())) == 0

        ## Store assumptions and guarantees
        self._assumptions = tl_assumptions
        self._guarantees = tl_guarantees

    @cached_property
    def assumptions(self):
        return self._assumptions

    @cached_property
    def guarantees(self):
        return self._guarantees

    def verify(self, generateBatchApprox):
        sub_results = [stmt.verify(generateBatchApprox) for stmt in self.sub_stmts]
        return CompositionContractResult(
            self.assumptions, self.guarantees, self.component, sub_results
        )

    def tempVarName(self):
        var_name = f"SCENIC_INTERNAL_VAR_{self.var_num}"
        self.var_num += 1
        return var_name

    @staticmethod
    def isTempVar(var):
        return var.startswith("SCENIC_INTERNAL_VAR_")

    @staticmethod
    def extractTempVars(var_iterable):
        return {var for var in var_iterable if Composition.isTempVar(var)}


class CompositionContractResult(ContractResult):
    def __init__(self, assumptions, guarantees, component, sub_results):
        super().__init__(assumptions, guarantees, component)
        self.sub_results = sub_results

    @cached_property
    def correctness(self):
        correctness_gaps = [1 - result.correctness for result in self.sub_results]
        overall_correctness_gap = sum(correctness_gaps)
        return max(0, 1 - overall_correctness_gap)

    @cached_property
    def confidence(self):
        return prod(result.confidence for result in self.sub_results)

    @property
    def evidenceSummary(self):
        return "\n".join(str(result) for result in self.sub_results)


class WeakMerge(VerificationTechnique):
    def __init__(self, sub_stmts, component, environment):
        ## Initialization ##
        # Store parameters
        self.component = component
        self.sub_stmts = sub_stmts
        self.environment = environment

        # Ensure all sub statements are of a valid form
        for stmt in self.sub_stmts:
            assert isinstance(stmt, VerificationTechnique)

        # Check that all sub-statements are applied to this component
        for stmt in self.sub_stmts:
            assert stmt.component is self.component

        def conjoin_list(l):
            return specs.And(subs=deepcopy(l)) if len(l) > 1 else deepcopy(l[0])

        a_conjunctions = tuple(conjoin_list(stmt.assumptions) for stmt in self.sub_stmts)
        g_conjunctions = tuple(conjoin_list(stmt.guarantees) for stmt in self.sub_stmts)

        self._assumptions = (specs.Or(subs=a_conjunctions),)
        self._guarantees = []
        banned_assums = None
        for ac, gc in zip(a_conjunctions, g_conjunctions):
            if banned_assums is None:
                target_assumption = ac
                banned_assums = specs.Not(sub=ac)
            else:
                target_assumption = specs.And(subs=[ac, banned_assums])
                banned_assums = specs.And(subs=[banned_assums, specs.Not(ac)])

            implication = specs.Implies(sub1=target_assumption,sub2=gc)
            self._guarantees.append(implication)
        self._guarantees = tuple(self._guarantees)

        self.static_assumptions = {stmt: all(WeakMerge.checkStatic(a) for a in stmt.assumptions) for stmt in self.sub_stmts}

        # TODO: Remove limitation of 2 sub-contracts with one "confirmed"
        is_confirmed = lambda s: isinstance(s, LeanContractProof) or (isinstance(s, Assumption) and s.correctness == 1)

        if (len(sub_stmts) == 2
            and sum(self.static_assumptions.values()) >= 1
            and len(tuple(filter(is_confirmed, sub_stmts))) >= 1
            ):
            self.weak_merge_speedup = True
        else:
            self.weak_merge_speedup = False

    @cached_property
    def assumptions(self):
        return self._assumptions

    @cached_property
    def guarantees(self):
        return self._guarantees

    def verify(self, generateBatchApprox):
        if self.weak_merge_speedup:
            safe_results = 0
            unsafe_results = 0

            safe_contracts = [stmt for stmt, static in self.static_assumptions.items()
                if static and not isinstance(stmt, Testing)]
            assert len(safe_contracts) == 1
            safe_contract = safe_contracts[0]
            unsafe_contracts = [stmt for stmt in self.sub_stmts if stmt not in safe_contracts]
            assert len(unsafe_contracts) == 1
            unsafe_contract = unsafe_contracts[0]
            assert safe_contract != unsafe_contract

            # Add intercept to generateBatchApprox hook
            def _generateBatchApprox(scenario, **kwargs):
                nonlocal safe_results
                nonlocal unsafe_results

                results = generateBatchApprox(scenario, **kwargs)
                results_safety = [all(WeakMerge._evaluateSpecification(a, scene)
                    for a in safe_contract.assumptions)
                    for scene in results]

                safe_results += sum(results_safety)
                passthrough_results = [result for result, safe in zip(results, results_safety) if not safe]
                unsafe_results += len(passthrough_results)

                return passthrough_results

            sub_results = [stmt.verify(_generateBatchApprox) for stmt in self.sub_stmts]
            sub_results_dict = dict(zip(self.sub_stmts, sub_results))

            rejection_prob = sub_results_dict[unsafe_contract].r_count/len(sub_results_dict[unsafe_contract].testData)

            heuristic_result = SimulationTestingContractResult(self.assumptions, self.guarantees,
                self.component, sub_results_dict[unsafe_contract]._confidence, None)
            heuristic_result.addTests(sub_results_dict[unsafe_contract].testData)
            heuristic_result.addTests([SimulationTestData(TestResult.V, [], None, None, 0)
                for _ in range(math.floor((1-rejection_prob)*safe_results))])
            heuristic_result.addTests([SimulationTestData(TestResult.R, [], None, None, 0)
                for _ in range(math.ceil((rejection_prob)*safe_results))])

            return WeakMergeContractResult(
                self.assumptions,
                self.guarantees,
                self.component,
                sub_results,
                heuristic_result=heuristic_result,
            )
        else:
            sub_results = [stmt.verify(generateBatchApprox) for stmt in self.sub_stmts]
            return WeakMergeContractResult(
                self.assumptions,
                self.guarantees,
                self.component,
                sub_results,
                heuristic_result=None,
            )

    @staticmethod
    def checkStatic(spec):
        if isinstance(spec, (specs.Always, specs.Eventually, specs.Next, specs.Until)):
            return False

        if isinstance(spec, specs.Atomic):
            if (isinstance(spec.ast, ast.Subscript)
                and isinstance(spec.ast.value, ast.Name)
                and spec.ast.value.id == 'params'):
                return True
            return False
        elif isinstance(spec, specs.ConstantSpecNode):
            return True
        elif isinstance(spec, specs.UnarySpecNode):
            return WeakMerge.checkStatic(spec.sub)
        elif isinstance(spec, specs.BinarySpecNode):
            return WeakMerge.checkStatic(spec.sub1) and WeakMerge.checkStatic(spec.sub2)
        elif isinstance(spec, specs.NarySpecNode):
            return all(WeakMerge.checkStatic(sub) for sub in spec.subs)

        assert False

    @staticmethod
    def _evaluateSpecification(spec, scene):
        if isinstance(spec, specs.Atomic):
            assert (isinstance(spec.ast, ast.Subscript)
                and isinstance(spec.ast.value, ast.Name)
                and spec.ast.value.id == 'params')
            return scene.params[spec.ast.slice.value]

        elif isinstance(spec, specs.ConstantSpecNode):
            return spec.value

        elif isinstance(spec, specs.UnarySpecNode):
            sub = WeakMerge._evaluateSpecification(spec.sub, scene)
            if isinstance(spec, specs.Not):
                return not sub
            elif isinstance(spec, specs.Neg):
                return -1*sub
            elif isinstance(spec, specs.Ceil):
                return math.ceil(sub)
            else:
                assert False

        elif isinstance(spec, specs.BinarySpecNode):
            sub1 = WeakMerge._evaluateSpecification(spec.sub1, scene)
            sub2 = WeakMerge._evaluateSpecification(spec.sub2, scene)

            if isinstance(spec, specs.Implies):
                return (not sub1) or sub2
            elif isinstance(spec, specs.Equal):
                return sub1 == sub2
            elif isinstance(spec, specs.GT):
                return sub1 > sub2
            elif isinstance(spec, specs.GE):
                return sub1 >= sub2
            elif isinstance(spec, specs.LT):
                return sub1 < sub2
            elif isinstance(spec, specs.LE):
                return sub1 <= sub2
            elif isinstance(spec, specs.Add):
                return sub1 + sub2
            elif isinstance(spec, specs.Sub):
                return sub1 - sub2
            elif isinstance(spec, specs.Mul):
                return sub1 * sub2
            elif isinstance(spec, specs.Div):
                return sub1 / sub2
            elif isinstance(spec, specs.Min):
                return min(sub1, sub2)
            elif isinstance(spec, specs.Max):
                return max(sub1, sub2)
            else:
                assert False

        elif isinstance(spec, specs.NarySpecNode):
            subs = [WeakMerge._evaluateSpecification(sub, scene) for sub in spec.subs]

            if isinstance(spec, specs.And):
                return reduce(lambda x, y: x and y, subs)
            elif isinstance(spec, specs.Or):
                return reduce(lambda x, y: x or y, subs)
        else:
            assert False


class WeakMergeContractResult(ContractResult):
    def __init__(self, assumptions, guarantees, component, sub_results, heuristic_result):
        super().__init__(assumptions, guarantees, component)
        self.sub_results = sub_results
        self.heuristic_result = heuristic_result

    @cached_property
    def correctness(self):
        if self.heuristic_result is not None:
            return self.heuristic_result.correctness
        else:
            # Fall back to union bound if we can't apply heuristic
            correctness_gaps = [1 - result.correctness for result in self.sub_results]
            overall_correctness_gap = sum(correctness_gaps)
            return max(0, 1 - overall_correctness_gap)

    @cached_property
    def confidence(self):
        if self.heuristic_result is not None:
            return self.heuristic_result.confidence
        else:
            return prod(result.confidence for result in self.sub_results)

    @property
    def evidenceSummary(self):
        summary = "Conjunction Result:\n"
        if self.heuristic_result is not None:
            summary += self.heuristic_result.evidenceSummary.replace("\n", "\n    ") + "\n"
        for i, result in enumerate(self.sub_results):
            summary += f"Sub Result (Correctness={result.correctness:.2f}):\n{result}\n"
        return summary
