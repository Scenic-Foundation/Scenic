import ast
from copy import copy
from enum import IntFlag, auto
import itertools
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

from scenic.core.errors import ScenicParseError, getText
import scenic.syntax.ast as s

# exposed functions


def compileScenicAST(
    scenicAST: ast.AST,
    *,
    filename: str = "<unknown>",
    inBehavior: bool = False,
    inMonitor: bool = False,
    inCompose: bool = False,
    inSetup: bool = False,
    inInterruptBlock: bool = False,
) -> Tuple[Union[ast.AST, List[ast.AST]], List[ast.AST]]:
    """Compiles Scenic AST to Python AST"""
    compiler = ScenicToPythonTransformer(filename)

    # set optional flags
    compiler.inBehavior = inBehavior
    compiler.inMonitor = inMonitor
    compiler.inCompose = inCompose
    compiler.inSetup = inSetup
    compiler.inInterruptBlock = inInterruptBlock

    tree = compiler.visit(scenicAST)
    if isinstance(tree, list):
        node = [ast.fix_missing_locations(n) for n in tree]
    else:
        node = ast.fix_missing_locations(tree)
    return node, compiler.requirements


# constants

temporaryName = "_Scenic_temporary_name"
behaviorArgName = "_Scenic_current_behavior"
checkPreconditionsName = "checkPreconditions"
checkInvariantsName = "checkInvariants"
interruptPrefix = "_Scenic_interrupt"

abortFlag = ast.Attribute(ast.Name("BlockConclusion", ast.Load()), "ABORT", ast.Load())
breakFlag = ast.Attribute(ast.Name("BlockConclusion", ast.Load()), "BREAK", ast.Load())
continueFlag = ast.Attribute(
    ast.Name("BlockConclusion", ast.Load()), "CONTINUE", ast.Load()
)
returnFlag = ast.Attribute(ast.Name("BlockConclusion", ast.Load()), "RETURN", ast.Load())
finishedFlag = ast.Attribute(
    ast.Name("BlockConclusion", ast.Load()), "FINISHED", ast.Load()
)

trackedNames = {"ego", "workspace"}
globalParametersName = "globalParameters"
builtinNames = {globalParametersName, "str", "int", "float"}


# shorthands for convenience

loadCtx = ast.Load()
ego = ast.Name("ego")

noArgs = ast.arguments(
    posonlyargs=[],
    args=[],
    vararg=None,
    kwonlyargs=[],
    kw_defaults=[],
    kwarg=None,
    defaults=[],
)
selfArg = ast.arguments(
    posonlyargs=[],
    args=[ast.arg(arg="self", annotation=None)],
    vararg=None,
    kwonlyargs=[],
    kw_defaults=[],
    kwarg=None,
    defaults=[],
)
initialBehaviorArgs = [
    ast.arg(arg=behaviorArgName, annotation=None),
    ast.arg(arg="self", annotation=None),
]
onlyBehaviorArgs = ast.arguments(
    posonlyargs=[],
    args=initialBehaviorArgs,
    vararg=None,
    kwonlyargs=[],
    kw_defaults=[],
    kwarg=None,
    defaults=[],
)

# helpers


class AttributeFinder(ast.NodeVisitor):
    """Utility class for finding all referenced attributes of a given name."""

    @staticmethod
    def find(target, node):
        af = AttributeFinder(target)
        af.visit(node)
        return af.attributes, af.rawLoc

    def __init__(self, target):
        super().__init__()
        self.target = target
        self.attributes = set()
        self.rawLoc = None

    def visit_Attribute(self, node):
        val = node.value
        if isinstance(val, ast.Name) and val.id == self.target:
            self.attributes.add(node.attr)
            return
        self.visit(val)

    def visit_Name(self, node):
        if node.id == self.target:
            self.rawLoc = node


class LocalFinder(ast.NodeVisitor):
    """Utility class for finding all local variables of a code block."""

    @staticmethod
    def findIn(block):
        lf = LocalFinder()
        for statement in block:
            lf.visit(statement)
        names = lf.names
        return names - lf.globals - lf.nonlocals

    def __init__(self):
        self.names = set()
        self.globals = set()
        self.nonlocals = set()

    def visit_Global(self, node):
        self.globals.update(node.names)

    def visit_Nonlocal(self, node):
        self.nonlocals.update(node.names)

    def visit_FunctionDef(self, node):
        self.names.add(node.name)
        self.visit(node.args)
        for decorator in node.decorator_list:
            self.visit(decorator)
        if node.returns is not None:
            self.visit(node.returns)
        # do not visit body; it's another block

    def visit_Lambda(self, node):
        self.visit(node.args)
        # do not visit body; it's another block

    def visit_ClassDef(self, node):
        self.names.add(node.name)
        for child in itertools.chain(node.bases, node.keywords, node.decorator_list):
            self.visit(child)
        # do not visit body; it's another block

    def visit_Import(self, node):
        for alias in node.names:
            bound = alias.asname
            if bound is None:
                bound = alias.name
            self.names.add(bound)

    def visit_ImportFrom(self, node):
        self.visit_Import(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_ExceptHandler(self, node):
        if node.name is not None:
            self.names.add(node.name)
        self.generic_visit(node)


class Transformer(ast.NodeTransformer):
    """Subclass of `ast.NodeTransformer` with a method for raising syntax errors."""

    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def makeSyntaxError(self, msg, node: ast.AST) -> ScenicParseError:
        e = SyntaxError(msg)
        e.lineno = node.lineno
        e.offset = node.col_offset
        if node.end_lineno is not None:
            e.end_lineno = node.end_lineno
        if node.end_col_offset is not None:
            e.end_offset = node.end_col_offset
        e.filename = self.filename
        raise ScenicParseError(e)


# Proposition Constructors with Temporal Operators Support
PROPOSITION_AND = "PropositionAnd"
PROPOSITION_OR = "PropositionOr"
PROPOSITION_NOT = "PropositionNot"
ATOMIC_PROPOSITION = "AtomicProposition"
ALWAYS = "Always"
EVENTUALLY = "Eventually"
NEXT = "Next"
UNTIL = "Until"
IMPLIES = "Implies"
PROPOSITION_FACTORY = (
    PROPOSITION_AND,
    PROPOSITION_OR,
    PROPOSITION_NOT,
    ATOMIC_PROPOSITION,
    ALWAYS,
    EVENTUALLY,
    NEXT,
    UNTIL,
    IMPLIES,
)
TEMPORAL_PREFIX_OPS = {
    "always",
    "eventually",
    "next",
}


class AtomicCheckTransformer(Transformer):
    def visit_Call(self, node: ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in TEMPORAL_PREFIX_OPS:
            self.makeSyntaxError(
                f'malformed use of the "{func.id}" temporal operator', node
            )
        return self.generic_visit(node)


class PropositionTransformer(Transformer):
    def __init__(self, filename="<unknown>") -> None:
        super().__init__(filename)
        self.nextSyntaxId = 0

    def transform(
        self, node: ast.AST, nextSyntaxId=0
    ) -> Tuple[ast.AST, List[ast.AST], int]:
        """`transform` takes an AST node and apply transformations needed for temporal evaluation

        Args:
            node (ast.AST): AST node to perform proposition transformation
            nextSyntaxId (int, optional): Assign syntax ids starting at this number. Defaults to 0.

        Returns:
            ast.AST: Transformed AST node
        """
        self.nextSyntaxId = nextSyntaxId
        wrapped = self.visit(ast.fix_missing_locations(node))
        if self.is_proposition_factory(wrapped):
            return wrapped, self.nextSyntaxId
        newNode = self._create_atomic_proposition_factory(node)
        return newNode, self.nextSyntaxId

    def generic_visit(self, node):
        acv = AtomicCheckTransformer(self.filename)
        acv.visit(node)
        return node

    def _register_requirement_syntax(self, syntax):
        """register requirement syntax for later use
        returns an ID for retrieving the syntax

        Args:
            propositionSyntax (ast.Node): AST Node that represents the requirement

        Returns:
            int: generated requirement syntax ID
        """
        syntaxId = self.nextSyntaxId
        self.nextSyntaxId += 1
        return syntaxId

    def _create_atomic_proposition_factory(self, node):
        """
        Given an expression, create an atomic proposition factory.

        Note: You must call `self.visit(node)` manually. This method does not make the surgeon visit the node.
        """
        lineNum = ast.Constant(node.lineno)
        ast.copy_location(lineNum, node)

        closure = ast.Lambda(noArgs, node)
        ast.copy_location(closure, node)

        syntaxId = self._register_requirement_syntax(node)
        syntaxIdConst = ast.Constant(syntaxId)
        ast.copy_location(syntaxIdConst, node)

        ap = ast.Call(
            func=ast.Name(id=ATOMIC_PROPOSITION, ctx=loadCtx),
            args=[closure],
            keywords=[
                ast.keyword(arg="syntaxId", value=syntaxIdConst),
            ],
        )
        ast.copy_location(ap, node)
        return ap

    def is_proposition_factory(self, node):
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in PROPOSITION_FACTORY
        )

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        """Convert a BoolOp node (`and`, `or`) to a corresponding proposition factory"""
        # 1. wrap each operand with a lambda function
        operands = []
        for operand in node.values:
            o = self.visit(operand)
            if self.is_proposition_factory(o):
                # if the operand is already an temporal requirement factory, keep it
                operands.append(self.visit(o))
                continue
            # if the operand is not an temporal requirement factory, make it an AP
            closure = self._create_atomic_proposition_factory(o)
            operands.append(closure)

        # 2. create a function call and pass operands
        boolOpToFunctionName = {
            ast.Or: "PropositionOr",
            ast.And: "PropositionAnd",
        }
        funcId = boolOpToFunctionName.get(type(node.op))
        newNode = ast.Call(
            func=ast.Name(id=funcId, ctx=ast.Load()),
            # pass a list of operands as the first argument
            args=[ast.copy_location(ast.List(elts=operands, ctx=ast.Load()), node)],
            keywords=[],
        )
        return ast.copy_location(newNode, node)

    def visit_UnaryOp(self, node):
        # rewrite `not` in requirements into a proposition factory
        if not isinstance(node.op, ast.Not):
            return self.generic_visit(node)

        lineNum = ast.Constant(node.lineno)
        ast.copy_location(lineNum, node)

        operand = self.visit(node.operand)

        newOperand = (
            operand
            if self.is_proposition_factory(operand)
            else self._create_atomic_proposition_factory(operand)
        )

        newNode = ast.Call(
            func=ast.Name(id=PROPOSITION_NOT, ctx=ast.Load()),
            args=[newOperand],
            keywords=[],
        )
        return ast.copy_location(newNode, node)

    def visit_Always(self, node: s.Always):
        value = self.visit(node.value)
        if not self.is_proposition_factory(value):
            value = self._create_atomic_proposition_factory(value)
        return ast.Call(
            func=ast.Name("Always", ctx=loadCtx),
            args=[value],
            keywords=[],
        )

    def visit_Eventually(self, node: s.Eventually):
        value = self.visit(node.value)
        if not self.is_proposition_factory(value):
            value = self._create_atomic_proposition_factory(value)
        return ast.Call(
            func=ast.Name("Eventually", ctx=loadCtx),
            args=[value],
            keywords=[],
        )

    def visit_Next(self, node: s.Next):
        value = self.visit(node.value)
        if not self.is_proposition_factory(value):
            value = self._create_atomic_proposition_factory(value)
        return ast.Call(
            func=ast.Name("Next", ctx=loadCtx),
            args=[value],
            keywords=[],
        )

    def visit_UntilOp(self, node: s.UntilOp):
        left = self.visit(node.left)
        if not self.is_proposition_factory(left):
            left = self._create_atomic_proposition_factory(left)
        right = self.visit(node.right)
        if not self.is_proposition_factory(right):
            right = self._create_atomic_proposition_factory(right)
        return ast.Call(
            func=ast.Name(id="Until", ctx=loadCtx),
            args=[self.visit(left), self.visit(right)],
            keywords=[],
        )

    def visit_ImpliesOp(self, node: s.ImpliesOp):
        hypothesis = self.visit(node.hypothesis)
        if not self.is_proposition_factory(hypothesis):
            hypothesis = self._create_atomic_proposition_factory(hypothesis)
        conclusion = self.visit(node.conclusion)
        if not self.is_proposition_factory(conclusion):
            conclusion = self._create_atomic_proposition_factory(conclusion)
        return ast.Call(
            func=ast.Name(id="Implies", ctx=loadCtx),
            args=[self.visit(hypothesis), self.visit(conclusion)],
            keywords=[],
        )


def unquote(s: str) -> str:
    if (s[:3] == s[-3:]) and s.startswith(("'''", '"""')):
        return s[3:-3]
    if (s[0] == s[-1]) and s.startswith(("'", '"')):
        return s[1:-1]
    return s


# transformer


class Context(IntFlag):
    TOP_LEVEL = auto()
    BEHAVIOR = auto()
    MONITOR = auto()
    COMPOSE = auto()
    DYNAMIC = BEHAVIOR | MONITOR | COMPOSE


class ScenicToPythonTransformer(Transformer):
    def __init__(self, filename) -> None:
        super().__init__(filename)

        self.requirements = []
        self.nextSyntaxId = 0

        self.inBehavior: bool = False
        "True if the transformer is processing behavior body"

        self.inMonitor: bool = False
        "True if the transformer is processing monitor body"

        self.behaviorLocals: set = set()
        "Set of variable names on the local scope of the behavior"

        self.inCompose: bool = False
        "True if the transformer is processing a `compose` block of modular scenario"

        self.inTryInterrupt = False
        self.inInterruptBlock = False
        self.inLoop = False
        self.usedBreak = False
        self.usedContinue = False

    @property
    def topLevel(self):
        return (
            not self.inBehavior
            and not self.inMonitor
            and not self.inCompose
            and not self.inTryInterrupt
        )

    def context(
        allowedContext: Context,
        errorBuilder: Optional[Callable[[str], str]] = None,
    ):
        "Mark AST node as only available inside certain contexts"

        def decorator(visitor: Callable[["ScenicToPythonTransformer", ast.AST], ast.AST]):
            def check_and_visit(self: "ScenicToPythonTransformer", node: ast.AST):
                ctx = None
                if self.topLevel and Context.TOP_LEVEL not in allowedContext:
                    ctx = "at the top level"
                elif self.inBehavior and Context.BEHAVIOR not in allowedContext:
                    ctx = "inside a behavior"
                elif self.inMonitor and Context.MONITOR not in allowedContext:
                    ctx = "inside a monitor"
                elif self.inCompose and Context.COMPOSE not in allowedContext:
                    ctx = "inside a compose block"
                if ctx:
                    raise self.makeSyntaxError(
                        (
                            f'Cannot use "{node.__class__.__name__}" {ctx}'
                            if errorBuilder is None
                            else errorBuilder(ctx)
                        ),
                        node,
                    )
                return visitor(self, node)

            return check_and_visit

        return decorator

    def generic_visit(self, node):
        if isinstance(node, s.AST):
            assert (
                False
            ), f'Scenic AST node "{node.__class__.__name__}" needs visitor in compiler'
        return super().generic_visit(node)

    # add support for list of nodes
    def visit(self, node: Union[ast.AST, List[ast.AST]]):
        if isinstance(node, ast.AST):
            return super().visit(node)
        elif isinstance(node, list):
            newStatements = []
            for statement in node:
                newStatement = self.visit(statement)
                if isinstance(newStatement, ast.AST):
                    newStatements.append(newStatement)
                else:
                    newStatements.extend(newStatement)
            return newStatements
        else:
            assert False, f"unknown object {node} encountered during compilation"

    # helper functions
    def _register_requirement_syntax(self, syntax: ast.AST) -> int:
        self.requirements.append(syntax)
        return len(self.requirements) - 1

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in builtinNames:
            if not isinstance(node.ctx, ast.Load):
                raise self.makeSyntaxError(f'unexpected keyword "{node.id}"', node)
            # Convert global parameters name to a call
            if node.id == globalParametersName:
                node = ast.copy_location(
                    ast.Call(ast.Name(node.id, loadCtx), [], []), node
                )
        elif node.id in trackedNames:
            if not isinstance(node.ctx, ast.Load):
                raise self.makeSyntaxError(
                    f'only simple assignments to "{node.id}" are allowed', node
                )
            node = ast.copy_location(ast.Call(ast.Name(node.id, loadCtx), [], []), node)
        elif node.id in self.behaviorLocals:
            lookup = ast.Attribute(ast.Name(behaviorArgName, loadCtx), node.id, node.ctx)
            return ast.copy_location(lookup, node)
        return node

    # hook control flow nodes to set appropriate flags for try-interrupt

    def visit_For(self, node):
        old = self.inLoop
        self.inLoop = True
        newNode = self.generic_visit(node)
        self.inLoop = old
        return newNode

    def visit_While(self, node):
        old = self.inLoop
        self.inLoop = True
        newNode = self.generic_visit(node)
        self.inLoop = old
        return newNode

    def visit_FunctionDef(self, node):
        oldInLoop, oldInInterruptBlock = self.inLoop, self.inInterruptBlock
        self.inLoop, self.inInterruptBlock = False, False
        newNode = self.generic_visit(node)
        self.inLoop, self.inInterruptBlock = oldInLoop, oldInInterruptBlock
        return newNode

    def visit_Break(self, node):
        if self.inInterruptBlock and not self.inLoop:
            if not self.usedBreak:
                self.usedBreak = node
            newNode = ast.Return(breakFlag)
            return ast.copy_location(newNode, node)
        else:
            return self.generic_visit(node)

    def visit_Continue(self, node):
        if self.inInterruptBlock and not self.inLoop:
            if not self.usedContinue:
                self.usedContinue = node
            newNode = ast.Return(continueFlag)
            return ast.copy_location(newNode, node)
        else:
            return self.generic_visit(node)

    def visit_Return(self, node):
        if self.inInterruptBlock:
            value = ast.Constant(None) if node.value is None else node.value
            ret = ast.Return(ast.Call(returnFlag, [value], []))
            return ast.copy_location(ret, node)
        else:
            return self.generic_visit(node)

    def visit_Yield(self, node):
        if self.inCompose or self.inBehavior:
            # `yield` statements are not allowed inside a compose/behavior block
            raise self.makeSyntaxError(
                "Cannot use `yield` inside a compose/behavior block", node
            )
        return self.generic_visit(node)

    def visit_YieldFrom(self, node):
        if self.inCompose or self.inBehavior:
            # `yield from` statements are not allowed inside a compose/behavior block
            raise self.makeSyntaxError(
                "Cannot use `yield from` inside a compose/behavior block", node
            )
        return self.generic_visit(node)

    # Special Case

    @context(Context.DYNAMIC)
    def visit_TryInterrupt(self, node: s.TryInterrupt):
        statements = []
        oldInTryInterrupt = self.inTryInterrupt

        self.inTryInterrupt = True

        oldInInterruptBlock, oldInLoop = self.inInterruptBlock, self.inLoop
        self.inInterruptBlock = True
        self.inLoop = False
        self.usedBreak = False
        self.usedContinue = False

        def makeInterruptBlock(name, body):
            newBody = self.visit(body)
            allLocals = sorted(LocalFinder.findIn(newBody))  # Sort for determinism
            if allLocals:
                newBody.insert(0, ast.Nonlocal(allLocals))
            newBody.append(ast.Return(finishedFlag))
            return ast.FunctionDef(name, onlyBehaviorArgs, newBody, [], None)

        bodyName = f"{interruptPrefix}_body"
        statements.append(makeInterruptBlock(bodyName, node.body))

        handlerNames, conditionNames = [], []
        for i, handler in enumerate(node.interrupt_when_handlers):
            condition = handler.cond
            block = handler.body

            handlerName = f"{interruptPrefix}_handler_{i}"
            handlerNames.append(handlerName)
            conditionName = f"{interruptPrefix}_condition_{i}"
            conditionNames.append(conditionName)

            statements.append(makeInterruptBlock(handlerName, block))
            self.inGuard = True
            checker = ast.Lambda(noArgs, self.visit(condition))
            self.inGuard = False
            defChecker = ast.Assign([ast.Name(conditionName, ast.Store())], checker)
            statements.append(defChecker)

        self.inInterruptBlock, self.inLoop = oldInInterruptBlock, oldInLoop
        self.inTryInterrupt = oldInTryInterrupt

        # Prepare tuples of interrupt conditions and handlers
        # (in order from high priority to low, so reversed relative to the syntax)
        conditions = ast.Tuple(
            [ast.Name(n, ast.Load()) for n in reversed(conditionNames)], ast.Load()
        )
        handlers = ast.Tuple(
            [ast.Name(n, ast.Load()) for n in reversed(handlerNames)], ast.Load()
        )

        # Construct code to execute the try-interrupt statement
        args = [
            ast.Name(behaviorArgName, ast.Load()),
            ast.Name("self", ast.Load()),
            ast.Name(bodyName, ast.Load()),
            conditions,
            handlers,
        ]
        callRuntime = ast.Call(ast.Name("runTryInterrupt", ast.Load()), args, [])
        runTI = ast.Assign(
            [ast.Name(temporaryName, ast.Store())], ast.YieldFrom(callRuntime)
        )
        statements.append(runTI)
        result = ast.Name(temporaryName, ast.Load())
        if self.usedBreak:
            test = ast.Compare(result, [ast.Is()], [breakFlag])
            brk = ast.copy_location(ast.Break(), self.usedBreak)
            statements.append(ast.If(test, [brk], []))
        if self.usedContinue:
            test = ast.Compare(result, [ast.Is()], [continueFlag])
            cnt = ast.copy_location(ast.Continue(), self.usedContinue)
            statements.append(ast.If(test, [cnt], []))
        test = ast.Compare(result, [ast.Is()], [returnFlag])
        retCheck = ast.If(
            test, [ast.Return(ast.Attribute(result, "return_value", ast.Load()))], []
        )
        statements.append(retCheck)

        # Construct overall try-except statement
        if node.except_handlers or node.finalbody:
            newTry = ast.Try(
                statements,
                [self.visit(handler) for handler in node.except_handlers],
                self.visit(node.orelse),
                self.visit(node.finalbody),
            )
            return ast.copy_location(newTry, node)
        else:
            return statements

    def visit_TrackedAssign(self, node: s.TrackedAssign):
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id=node.target.functionName, ctx=loadCtx),
                args=[self.visit(node.value)],
                keywords=[],
            )
        )

    def visit_InitialScenario(self, node: s.InitialScenario):
        return ast.copy_location(
            ast.Call(
                func=ast.Name(id="in_initial_scenario", ctx=loadCtx),
                args=[],
                keywords=[],
            ),
            node,
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        # use `Object` as base if none is specified
        if not node.bases:
            node.bases = [ast.Name("Object", loadCtx)]

        # annotated assignments are not allowed in Scenic classes
        # those should be parsed as property definitions instead
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign):
                raise self.makeSyntaxError(
                    "annotated assignments are not allowed in Scenic classes", stmt
                )

        # extract all property definitions
        propertyDefs: List[s.PropertyDef] = []
        newBody = []
        propSpot = None
        for stmt in node.body:
            if isinstance(stmt, s.PropertyDef):
                propertyDefs.append(stmt)
                if propSpot is None:
                    propSpot = len(newBody)
            else:
                newBody.append(stmt)

        # create dictionary from property name (str) to default values
        propertyDict = {}
        for propertyDef in propertyDefs:
            if propertyDef.property in propertyDict:
                raise self.makeSyntaxError(
                    f'duplicated property "{propertyDef.property}"', propertyDef
                )
            propertyDict[propertyDef.property] = propertyDef

        newBody.insert(
            len(newBody) if propSpot is None else propSpot,
            ast.Assign(
                targets=[ast.Name(id="_scenic_properties", ctx=ast.Store())],
                value=ast.Dict(
                    keys=[ast.Constant(value=p) for p in propertyDict.keys()],
                    values=[self.transformPropertyDef(v) for v in propertyDict.values()],
                ),
            ),
        )

        node.body = newBody
        return self.generic_visit(node)

    def transformPropertyDef(self, node: s.PropertyDef):
        properties, rawLoc = AttributeFinder.find("self", node.value)
        if rawLoc:
            self.makeSyntaxError(
                'cannot use raw name "self" in a default value (only "self.property")',
                rawLoc,
            )
        return ast.Call(
            func=ast.Name(id="_scenic_default", ctx=ast.Load()),
            args=[
                ast.Set(elts=[ast.Constant(value=p) for p in properties]),
                ast.Set(
                    elts=[ast.Constant(value=attr.keyword) for attr in node.attributes]
                ),
                ast.Lambda(
                    args=selfArg,
                    body=node.value,
                ),
            ],
            keywords=[],
        )

    def visit_PropertyDef(self, _: s.PropertyDef) -> Any:
        assert False, "PropertyDef should be handled in `visit_ClassDef`"

    @context(Context.TOP_LEVEL)
    def visit_BehaviorDef(self, node: s.BehaviorDef):
        return self.makeBehaviorLikeDef(
            baseClassName="Behavior",
            name=node.name,
            args=node.args,
            docstring=node.docstring,
            header=node.header,
            body=node.body,
        )

    @context(Context.TOP_LEVEL)
    def visit_MonitorDef(self, node: s.MonitorDef):
        return self.makeBehaviorLikeDef(
            baseClassName="Monitor",
            name=node.name,
            args=node.args,
            docstring=node.docstring,
            header=[],
            body=node.body,
        )

    @context(Context.TOP_LEVEL)
    def visit_ScenarioDef(self, node: s.ScenarioDef):
        # Set up arguments for setup and compose blocks
        args: ast.arguments = self.visit(node.args)
        args.posonlyargs = initialBehaviorArgs + args.posonlyargs

        # Get preconditions and invariants
        preconditions, invariants = self.separatePreconditionsAndInvariants(node.header)

        # Find all locals of the scenario, which will be shared amongst the various blocks
        allLocals = set()
        if node.compose:
            allLocals.update(LocalFinder.findIn(node.compose))
        if node.setup:
            allLocals.update(LocalFinder.findIn(node.setup))
        oldBL = self.behaviorLocals
        self.behaviorLocals = allLocals

        # Construct compose block
        self.inCompose = True
        guardCheckers = self.makeGuardCheckers(args, preconditions, invariants)
        if node.compose or preconditions or invariants:
            if node.compose:
                body = self.visit(node.compose)
            else:
                # generate no-op compose block to ensure invariants are checked
                wait = self.generateInvocation(node, ast.Constant(()))
                body = [ast.While(ast.Constant(True), wait, [])]
            compose = ast.FunctionDef("_compose", args, body, [], None)
        else:
            compose = ast.Assign([ast.Name("_compose", ast.Store())], ast.Constant(None))
        self.inCompose = False

        # Construct setup block
        self.inSetup = True
        if node.setup:
            setup = ast.FunctionDef("_setup", args, self.visit(node.setup), [], None)
        else:
            setup = ast.Assign([ast.Name("_setup", ast.Store())], ast.Constant(None))
        self.inSetup = False

        self.behaviorLocals = oldBL

        # Assemble scenario definition
        locs = ast.Constant(tuple(sorted(allLocals)))  # sort for AST determinism
        locs = ast.Call(ast.Name("frozenset", ast.Load()), [locs], [])
        saveLocals = ast.Assign([ast.Name("_locals", ast.Store())], locs)
        body = guardCheckers + [saveLocals, setup, compose]
        return ast.ClassDef(
            node.name, [ast.Name("DynamicScenario", loadCtx)], [], body, []
        )

    def makeGuardCheckers(
        self,
        args: ast.arguments,
        preconditions: List[s.Precondition],
        invariants: List[s.Invariant],
    ) -> List[ast.AST]:
        """Create a list of statements that defines precondition and invariant checker"""

        # Statements that check preconditions are satisfied
        preconditionChecks = []
        for precondition in preconditions:
            call = ast.Call(
                ast.Name("PreconditionViolation", loadCtx),
                [
                    ast.Name(behaviorArgName, loadCtx),
                    ast.Constant(precondition.lineno),
                ],
                [],
            )
            throw = ast.Raise(exc=call, cause=None)
            check = ast.If(
                test=ast.UnaryOp(ast.Not(), self.visit(precondition.value)),
                body=[throw],
                orelse=[],
            )

            chained_throw = ast.Raise(exc=call, cause=ast.Name("e", loadCtx))

            catch = ast.ExceptHandler(
                type=ast.Name("RejectionException", loadCtx),
                name="e",
                body=[chained_throw],
            )

            wrapped_check = ast.Try(
                body=[check], handlers=[catch], orelse=[], finalbody=[]
            )

            preconditionChecks.append(ast.copy_location(wrapped_check, precondition))

        definePreconditionChecker = ast.FunctionDef(
            checkPreconditionsName, args, preconditionChecks or [ast.Pass()], [], None
        )

        # Statements that check invariants are satisfied
        invariantChecks = []
        for invariant in invariants:
            call = ast.Call(
                ast.Name("InvariantViolation", loadCtx),
                [ast.Name(behaviorArgName, loadCtx), ast.Constant(invariant.lineno)],
                [],
            )
            throw = ast.Raise(exc=call, cause=None)
            check = ast.If(
                test=ast.UnaryOp(ast.Not(), self.visit(invariant.value)),
                body=[throw],
                orelse=[],
            )

            chained_throw = ast.Raise(exc=call, cause=ast.Name("e", loadCtx))

            catch = ast.ExceptHandler(
                type=ast.Name("RejectionException", loadCtx),
                name="e",
                body=[chained_throw],
            )

            wrapped_check = ast.Try(
                body=[check], handlers=[catch], orelse=[], finalbody=[]
            )

            invariantChecks.append(ast.copy_location(wrapped_check, invariant))

        defineInvariantChecker = ast.FunctionDef(
            checkInvariantsName, args, invariantChecks or [ast.Pass()], [], None
        )

        # assemble function body preamble
        preamble = [
            definePreconditionChecker,
            defineInvariantChecker,
        ]
        return preamble

    def separatePreconditionsAndInvariants(
        self, header: List[Union[s.Precondition, s.Invariant]]
    ) -> Tuple[List[s.Precondition], List[s.Invariant]]:
        """Given a list of preconditions and invariants, separate items into the list of preconditions and list of invariants

        Args:
            header (List[Union[s.Precondition, s.Invariant]]): List of preconditions and invariants

        Returns:
            Tuple[List[s.Precondition], List[s.Invariant]]: Tuple of precondition list and invariant list
        """
        preconditions: List[s.Precondition] = []
        invariants: List[s.Invariant] = []
        for n in header:
            if isinstance(n, s.Precondition):
                preconditions.append(n)
            elif isinstance(n, s.Invariant):
                invariants.append(n)
            else:
                assert False, f"Unexpected node type {n.__class__.__name__}"
        return (preconditions, invariants)

    def makeBehaviorLikeDef(
        self,
        baseClassName: Literal["Behavior", "Monitor"],
        name: str,
        args: Optional[ast.arguments],
        docstring: Optional[str],
        header: List[Union[s.Precondition, s.Invariant]],
        body: List[ast.AST],
    ):
        if baseClassName == "Behavior":
            ctxFlag = "inBehavior"
        elif baseClassName == "Monitor":
            ctxFlag = "inMonitor"
        else:
            assert False, f'Unexpected base class name "{baseClassName}"'

        # --- Extract preconditions and invariants ---
        preconditions, invariants = self.separatePreconditionsAndInvariants(header)

        # --- Copy arguments to the behavior object's namespace ---
        # list of all arguments
        allArgs = itertools.chain(args.posonlyargs, args.args, args.kwonlyargs)
        # statements that create argument variables
        copyArgs: List[ast.AST] = []
        for arg in allArgs:
            dest = ast.Attribute(ast.Name(behaviorArgName, loadCtx), arg.arg, ast.Store())
            copyArgs.append(
                ast.copy_location(ast.Assign([dest], ast.Name(arg.arg, loadCtx)), arg)
            )

        # --- Create a new `arguments` ---
        newArgs: ast.arguments = self.visit(args)
        # add private current behavior argument and implicit `self` argument
        newArgs.posonlyargs = initialBehaviorArgs + newArgs.posonlyargs

        # --- Process body ---
        setattr(self, ctxFlag, True)
        oldBehaviorLocals = self.behaviorLocals

        self.behaviorLocals = allLocals = LocalFinder.findIn(body)

        # handle docstring
        newBody = body
        docstringNode = []
        if docstring is not None:
            docstringNode = [ast.Expr(ast.Constant(unquote(docstring)))]

        # process body
        statements = self.visit(newBody)

        generatorBody = copyArgs + statements
        generatorDefinition = ast.FunctionDef(
            name="makeGenerator",
            args=newArgs,
            body=generatorBody,
            decorator_list=[],
            returns=None,
        )

        # --- Save local variables ---
        locs = ast.Constant(tuple(sorted(allLocals)))  # sort for AST determinism
        locs = ast.Call(ast.Name("frozenset", ast.Load()), [locs], [])
        saveLocals = ast.Assign([ast.Name("_locals", ast.Store())], locs)

        # --- Guards ---
        guardCheckers = self.makeGuardCheckers(newArgs, preconditions, invariants)

        # --- Create class definition ---
        classBody = docstringNode + guardCheckers + [saveLocals, generatorDefinition]
        classDefinition = ast.ClassDef(
            name, [ast.Name(baseClassName, loadCtx)], [], classBody, []
        )

        setattr(self, ctxFlag, False)
        self.behaviorLocals = oldBehaviorLocals

        return classDefinition

    def visit_Call(self, node: ast.Call) -> Any:
        newArgs = []
        wrappedStar = False
        for arg in node.args:
            if isinstance(arg, ast.Starred) and not self.inBehavior:
                wrappedStar = True
                checkedVal = ast.Call(
                    ast.Name("wrapStarredValue", ast.Load()),
                    [self.visit(arg.value), ast.Constant(arg.value.lineno)],
                    [],
                )
                newArgs.append(ast.Starred(checkedVal, ast.Load()))
            else:
                newArgs.append(self.visit(arg))
        newKeywords = [self.visit(kwarg) for kwarg in node.keywords]
        newFunc = self.visit(node.func)

        # Convert primitive type conversions to their Scenic equivalents
        if isinstance(newFunc, ast.Name):
            if newFunc.id == "str":
                newFunc.id = "_toStrScenic"
            elif newFunc.id == "float":
                newFunc.id = "_toFloatScenic"
            elif newFunc.id == "int":
                newFunc.id = "_toIntScenic"

        if wrappedStar:
            newNode = ast.Call(
                ast.Name("callWithStarArgs", ast.Load()),
                [newFunc] + newArgs,
                newKeywords,
            )
        else:
            newNode = ast.Call(newFunc, newArgs, newKeywords)
        newNode = ast.copy_location(newNode, node)
        return newNode

    @context(Context.TOP_LEVEL)
    def visit_Model(self, node: s.Model):
        if self.inSetup:
            raise self.makeSyntaxError('Cannot use "model" inside a setup block', node)
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id="model", ctx=loadCtx),
                args=[
                    ast.Name(id="_Scenic_module_namespace", ctx=loadCtx),
                    ast.Constant(value=node.name),
                ],
                keywords=[],
            )
        )

    @context(Context.TOP_LEVEL)
    def visit_Mutate(self, node: s.Mutate):
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id="mutate", ctx=loadCtx),
                args=[self.visit(el) for el in node.elts],
                keywords=(
                    [ast.keyword(arg="scale", value=self.visit(node.scale))]
                    if node.scale is not None
                    else []
                ),
            )
        )

    @context(Context.TOP_LEVEL)
    def visit_Param(self, node: s.Param):
        d = dict()
        for parameter in node.elts:
            if parameter.identifier in d:
                raise self.makeSyntaxError(
                    f'Duplicated param "{parameter.identifier}"', node
                )
            d[parameter.identifier] = self.visit(parameter.value)
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id="param", ctx=loadCtx),
                args=[
                    ast.Dict(
                        [ast.Constant(k) for k in d.keys()],
                        list(d.values()),
                    )
                ],
                keywords=[],
            )
        )

    def visit_Require(self, node: s.Require):
        prob = node.prob
        if prob is not None:
            if not 0 <= prob <= 1:
                raise self.makeSyntaxError("probability must be between 0 and 1", node)
            kwargs = {"prob": ast.Constant(prob)}
        else:
            kwargs = {}

        return self.createRequirementLike(
            "require", node.cond, node.lineno, node.name, kwargs
        )

    def visit_RequireMonitor(self, node: s.RequireMonitor):
        return self.createRequirementLike(
            "require_monitor", node.monitor, node.lineno, node.name
        )

    def visit_Override(self, node: s.Override):
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id="override", ctx=loadCtx),
                args=[self.visit(node.target)] + [self.visit(s) for s in node.specifiers],
                keywords=[],
            )
        )

    def visit_Abort(self, node: s.Abort):
        if not self.inInterruptBlock:
            raise self.makeSyntaxError(
                "`abort` can only be used inside an interrupt block", node
            )
        return ast.copy_location(
            ast.Return(abortFlag),
            node,
        )

    @context(Context.BEHAVIOR)
    def visit_Take(self, node: s.Take):
        action = ast.Tuple(self.visit(node.elts), loadCtx)
        return self.generateInvocation(node, ast.copy_location(action, node))

    @context(Context.DYNAMIC)
    def visit_Wait(self, node: s.Wait):
        return self.generateInvocation(node, ast.Constant(()))

    @context(Context.DYNAMIC)
    def visit_WaitFor(self, node: s.WaitFor):
        modifier = ast.Call(
            func=ast.Name("Modifier", loadCtx),
            args=[
                ast.Constant("for"),
                self.visit(node.duration.value),
                ast.Constant(node.duration.unitStr),
            ],
            keywords=[],
        )
        return self.makeDoLike(node, [], modifier=modifier)

    @context(Context.DYNAMIC)
    def visit_WaitUntil(self, node: s.WaitUntil):
        modifier = ast.Call(
            func=ast.Name("Modifier", loadCtx),
            args=[ast.Constant("until"), ast.Lambda(noArgs, self.visit(node.cond))],
            keywords=[],
        )
        return self.makeDoLike(node, [], modifier=modifier)

    @context(Context.DYNAMIC)
    def visit_Terminate(self, node: s.Terminate):
        termination = ast.Call(
            ast.Name("_makeTerminationAction", loadCtx),
            [ast.Name("self", ast.Load()), ast.Constant(node.lineno)],
            [],
        )
        return self.generateInvocation(node, termination)

    @context(Context.DYNAMIC)
    def visit_TerminateSimulation(self, node: s.TerminateSimulation):
        termination = ast.Call(
            ast.Name("_makeSimulationTerminationAction", loadCtx),
            [ast.Constant(node.lineno)],
            [],
        )
        return self.generateInvocation(node, termination)

    @context(Context.DYNAMIC)
    def visit_Do(self, node: s.Do):
        if (self.inBehavior or self.inMonitor) and len(node.elts) > 1:
            raise self.makeSyntaxError(
                f"`do` can only take one action inside a {'behavior' if self.inBehavior else 'monitor'}",
                node,
            )
        return self.makeDoLike(node, node.elts)

    @context(Context.DYNAMIC)
    def visit_DoFor(self, node: s.DoFor):
        if (self.inBehavior or self.inMonitor) and len(node.elts) > 1:
            raise self.makeSyntaxError(
                f"`do` can only take one action inside a {'behavior' if self.inBehavior else 'monitor'}",
                node,
            )
        return self.makeDoLike(
            node,
            node.elts,
            modifier=ast.Call(
                func=ast.Name("Modifier", loadCtx),
                args=[
                    ast.Constant("for"),
                    self.visit(node.duration.value),
                    ast.Constant(node.duration.unitStr),
                ],
                keywords=[],
            ),
        )

    @context(Context.DYNAMIC)
    def visit_DoUntil(self, node: s.DoUntil):
        if (self.inBehavior or self.inMonitor) and len(node.elts) > 1:
            raise self.makeSyntaxError(
                f"`do` can only take one action inside a {'behavior' if self.inBehavior else 'monitor'}",
                node,
            )
        return self.makeDoLike(
            node,
            node.elts,
            modifier=ast.Call(
                func=ast.Name("Modifier", loadCtx),
                args=[
                    ast.Constant("until"),
                    ast.Lambda(noArgs, self.visit(node.cond)),
                ],
                keywords=[],
            ),
        )

    @context(Context.DYNAMIC)
    def visit_DoChoose(self, node: s.DoChoose):
        return self.makeDoLike(node, node.elts, schedule="choose")

    @context(Context.DYNAMIC)
    def visit_DoShuffle(self, node: s.DoChoose):
        return self.makeDoLike(node, node.elts, schedule="shuffle")

    def generateInvocation(self, node: ast.AST, actionlike, invoker=ast.Yield):
        """Generate an invocation of an action, behavior, or scenario."""
        invokeAction = ast.Expr(invoker(actionlike))
        checker = ast.Attribute(
            ast.Name(behaviorArgName, loadCtx), checkInvariantsName, loadCtx
        )
        args = ast.Starred(
            ast.Attribute(ast.Name(behaviorArgName, loadCtx), "_args", loadCtx), loadCtx
        )
        kwargs = ast.keyword(
            None, ast.Attribute(ast.Name(behaviorArgName, loadCtx), "_kwargs", loadCtx)
        )
        checkInvariants = ast.Expr(
            ast.Call(checker, [ast.Name("self", loadCtx), args], [kwargs])
        )
        ast.copy_location(invokeAction, node)
        ast.copy_location(checkInvariants, node)
        return [
            invokeAction,
            checkInvariants,
        ]

    def makeDoLike(
        self,
        node: ast.AST,
        elts: List[ast.AST],
        modifier: Optional[ast.Call] = None,
        schedule: Optional[str] = None,
    ):
        subHandler = ast.Attribute(
            ast.Name(behaviorArgName, loadCtx), "_invokeSubBehavior", loadCtx
        )
        subArgs = [
            ast.Name("self", loadCtx),
            ast.Tuple([self.visit(e) for e in elts], loadCtx),
        ]
        if modifier is not None:
            subArgs.append(modifier)
        keywords = []
        if schedule is not None:
            keywords = [ast.keyword("schedule", ast.Constant(schedule))]
        subRunner = ast.Call(subHandler, subArgs, keywords)
        return self.generateInvocation(node, subRunner, ast.YieldFrom)

    @context(Context.TOP_LEVEL)
    def visit_Record(self, node: s.Record):
        if node.name and node.recorder:
            raise self.makeSyntaxError(
                'cannot use both "as" and "to" in "record" statement', node
            )
        kwargs = {}
        if node.recorder:
            kwargs["recorder"] = self.visit(node.recorder)
        if node.period:
            elts = [self.visit(node.period.value), ast.Constant(node.period.unitStr)]
            kwargs["period"] = ast.Tuple(elts, loadCtx)
        if node.delay:
            elts = [self.visit(node.delay.value), ast.Constant(node.delay.unitStr)]
            kwargs["delay"] = ast.Tuple(elts, loadCtx)

        return self.createRequirementLike(
            "record", node.value, node.lineno, node.name, kwargs
        )

    @context(Context.TOP_LEVEL)
    def visit_RecordInitial(self, node: s.RecordInitial):
        return self.createRequirementLike(
            "record_initial", node.value, node.lineno, node.name
        )

    @context(Context.TOP_LEVEL)
    def visit_RecordFinal(self, node: s.RecordFinal):
        return self.createRequirementLike(
            "record_final", node.value, node.lineno, node.name
        )

    @context(Context.TOP_LEVEL)
    def visit_TerminateWhen(self, node: s.TerminateWhen):
        return self.createRequirementLike(
            "terminate_when", node.cond, node.lineno, node.name
        )

    @context(Context.TOP_LEVEL)
    def visit_TerminateSimulationWhen(self, node: s.TerminateSimulationWhen):
        return self.createRequirementLike(
            "terminate_simulation_when", node.cond, node.lineno, node.name
        )

    def createRequirementLike(
        self,
        functionName: str,
        body: ast.AST,
        lineno: int,
        name: Optional[str] = None,
        kwargs: Dict[str, Union[Tuple[ast.AST, ...], ast.AST]] = {},
    ):
        """Create a call to a function that implements requirement-like features, such as `record` and `terminate when`.

        Args:
            functionName (str): Name of the requirement-like function to call. Its signature
                must be `(reqId: int, body: () -> bool, lineno: int, name: str | None)`
            body (ast.AST): AST node to evaluate for checking the condition
            lineno (int): Line number in the source code
            name (Optional[str], optional): Optional name for requirements. Defaults to None.
            kwargs: Optional keyword arguments.
        """
        propTransformer = PropositionTransformer(self.filename)
        newBody, self.nextSyntaxId = propTransformer.transform(body, self.nextSyntaxId)
        newBody = self.visit(newBody)
        requirementId = self._register_requirement_syntax(body)

        keywords = []
        for datum, node in kwargs.items():
            if isinstance(node, tuple):
                node = ast.Tuple(*node)
            keywords.append(ast.keyword(arg=datum, value=node))

        return ast.Expr(
            value=ast.Call(
                func=ast.Name(functionName, loadCtx),
                args=[
                    ast.Constant(requirementId),  # requirement ID
                    newBody,  # body
                    ast.Constant(lineno),  # line number
                    ast.Constant(name),  # requirement name
                ],
                keywords=keywords,
            )
        )

    @context(Context.TOP_LEVEL)
    def visit_TerminateAfter(self, node: s.TerminateAfter):
        return ast.copy_location(
            ast.Expr(
                ast.Call(
                    func=ast.Name(id="terminate_after", ctx=loadCtx),
                    args=[
                        self.visit(node.duration.value),
                        ast.Constant(node.duration.unitStr),
                    ],
                    keywords=[],
                )
            ),
            node,
        )

    @context(Context.TOP_LEVEL)
    def visit_Simulator(self, node: s.Simulator):
        return ast.copy_location(
            ast.Expr(
                ast.Call(
                    func=ast.Name(id="simulator", ctx=loadCtx),
                    args=[ast.Lambda(noArgs, self.visit(node.value))],
                    keywords=[],
                )
            ),
            node,
        )

    # Instance & Specifier

    # N.B. We can't use @context(Context.TOP_LEVEL) here because we actually
    # allow `new Point` anywhere; we'll catch `new Object` inside behaviors in
    # the veneer object registration code.
    def visit_New(self, node: s.New):
        return ast.Call(
            func=ast.Name(id="new", ctx=loadCtx),
            args=[
                ast.Name(id=node.className, ctx=loadCtx),
                ast.List(elts=[self.visit(s) for s in node.specifiers], ctx=ast.Load()),
            ],
            keywords=[],
        )

    def visit_WithSpecifier(self, node: s.WithSpecifier):
        return ast.Call(
            func=ast.Name(id="With", ctx=loadCtx),
            args=[
                ast.Constant(value=node.prop),
                self.visit(node.value),
            ],
            keywords=[],
        )

    def visit_AtSpecifier(self, node: s.AtSpecifier):
        return ast.Call(
            func=ast.Name(id="At", ctx=loadCtx),
            args=[self.visit(node.position)],
            keywords=[],
        )

    def visit_OffsetBySpecifier(self, node: s.OffsetBySpecifier):
        return ast.Call(
            func=ast.Name(id="OffsetBy", ctx=loadCtx),
            args=[
                self.visit(node.offset),
            ],
            keywords=[],
        )

    def visit_OffsetAlongSpecifier(self, node: s.OffsetAlongSpecifier):
        return ast.Call(
            func=ast.Name(id="OffsetAlongSpec", ctx=loadCtx),
            args=[
                self.visit(node.direction),
                self.visit(node.offset),
            ],
            keywords=[],
        )

    def visit_DirectionOfSpecifier(self, node: s.DirectionOfSpecifier):
        if isinstance(node.direction, s.LeftOf):
            fn = "LeftSpec"
        elif isinstance(node.direction, s.RightOf):
            fn = "RightSpec"
        elif isinstance(node.direction, s.AheadOf):
            fn = "Ahead"
        elif isinstance(node.direction, s.Behind):
            fn = "Behind"
        elif isinstance(node.direction, s.Above):
            fn = "Above"
        elif isinstance(node.direction, s.Below):
            fn = "Below"
        else:
            assert False, f"impossible direction {node.direction} in PositionSpecifier"
        return ast.Call(
            func=ast.Name(id=fn, ctx=loadCtx),
            args=[
                self.visit(node.position),
            ],
            keywords=(
                []
                if node.distance is None
                else [ast.keyword(arg="dist", value=self.visit(node.distance))]
            ),
        )

    def visit_BeyondSpecifier(self, node: s.BeyondSpecifier):
        return ast.Call(
            func=ast.Name(id="Beyond", ctx=loadCtx),
            args=[self.visit(node.position), self.visit(node.offset)],
            keywords=(
                [ast.keyword(arg="fromPt", value=self.visit(node.base))]
                if node.base is not None
                else []
            ),
        )

    def visit_VisibleSpecifier(self, node: s.VisibleSpecifier):
        if node.base is not None:
            return ast.Call(
                func=ast.Name(id="VisibleFrom", ctx=loadCtx),
                args=[self.visit(node.base)],
                keywords=[],
            )
        return ast.Call(
            func=ast.Name(id="VisibleSpec", ctx=loadCtx),
            args=[],
            keywords=[],
        )

    def visit_NotVisibleSpecifier(self, node: s.NotVisibleSpecifier):
        if node.base is not None:
            return ast.Call(
                func=ast.Name(id="NotVisibleFrom", ctx=loadCtx),
                args=[self.visit(node.base)],
                keywords=[],
            )
        return ast.Call(
            func=ast.Name(id="NotVisibleSpec", ctx=loadCtx),
            args=[],
            keywords=[],
        )

    def visit_InSpecifier(self, node: s.InSpecifier):
        return ast.Call(
            func=ast.Name(id="In", ctx=loadCtx),
            args=[self.visit(node.region)],
            keywords=[],
        )

    def visit_OnSpecifier(self, node: s.InSpecifier):
        return ast.Call(
            func=ast.Name(id="On", ctx=loadCtx),
            args=[self.visit(node.region)],
            keywords=[],
        )

    def visit_ContainedInSpecifier(self, node: s.InSpecifier):
        return ast.Call(
            func=ast.Name(id="ContainedIn", ctx=loadCtx),
            args=[self.visit(node.region)],
            keywords=[],
        )

    def visit_FollowingSpecifier(self, node: s.FollowingSpecifier):
        return ast.Call(
            func=ast.Name(id="Following", ctx=loadCtx),
            args=[self.visit(node.field), self.visit(node.distance)],
            keywords=(
                [ast.keyword(arg="fromPt", value=self.visit(node.base))]
                if node.base is not None
                else []
            ),
        )

    def visit_FacingSpecifier(self, node: s.FacingSpecifier):
        return ast.Call(
            func=ast.Name(id="Facing", ctx=loadCtx),
            args=[self.visit(node.heading)],
            keywords=[],
        )

    def visit_FacingTowardSpecifier(self, node: s.FacingTowardSpecifier):
        return ast.Call(
            func=ast.Name(id="FacingToward", ctx=loadCtx),
            args=[self.visit(node.position)],
            keywords=[],
        )

    def visit_FacingAwayFromSpecifier(self, node: s.FacingAwayFromSpecifier):
        return ast.Call(
            func=ast.Name(id="FacingAwayFrom", ctx=loadCtx),
            args=[self.visit(node.position)],
            keywords=[],
        )

    def visit_FacingDirectlyTowardSpecifier(self, node: s.FacingDirectlyTowardSpecifier):
        return ast.Call(
            func=ast.Name(id="FacingDirectlyToward", ctx=loadCtx),
            args=[self.visit(node.position)],
            keywords=[],
        )

    def visit_FacingDirectlyAwayFromSpecifier(
        self, node: s.FacingDirectlyAwayFromSpecifier
    ):
        return ast.Call(
            func=ast.Name(id="FacingDirectlyAwayFrom", ctx=loadCtx),
            args=[self.visit(node.position)],
            keywords=[],
        )

    def visit_ApparentlyFacingSpecifier(self, node: s.ApparentlyFacingSpecifier):
        return ast.Call(
            func=ast.Name(id="ApparentlyFacing", ctx=loadCtx),
            args=[self.visit(node.heading)],
            keywords=(
                [ast.keyword(arg="fromPt", value=self.visit(node.base))]
                if node.base is not None
                else []
            ),
        )

    # Operators

    def visit_RelativePositionOp(self, node: s.RelativePositionOp):
        return ast.Call(
            func=ast.Name(id="RelativePosition", ctx=loadCtx),
            args=[self.visit(node.target)],
            keywords=(
                []
                if node.base is None
                else [ast.keyword(arg="Y", value=self.visit(node.base))]
            ),
        )

    def visit_RelativeHeadingOp(self, node: s.RelativeHeadingOp):
        return ast.Call(
            func=ast.Name(id="RelativeHeading", ctx=loadCtx),
            args=[self.visit(node.target)],
            keywords=(
                []
                if node.base is None
                else [ast.keyword(arg="Y", value=self.visit(node.base))]
            ),
        )

    def visit_ApparentHeadingOp(self, node: s.ApparentHeadingOp):
        return ast.Call(
            func=ast.Name(id="ApparentHeading", ctx=loadCtx),
            args=[self.visit(node.target)],
            keywords=(
                []
                if node.base is None
                else [ast.keyword(arg="Y", value=self.visit(node.base))]
            ),
        )

    def visit_DistanceFromOp(self, node: s.DistanceFromOp):
        return ast.Call(
            func=ast.Name(id="DistanceFrom", ctx=loadCtx),
            args=[self.visit(node.target)],
            keywords=(
                [ast.keyword(arg="Y", value=self.visit(node.base))]
                if node.base is not None
                else []
            ),
        )

    def visit_MinDistanceFromOp(self, node: s.MinDistanceFromOp):
        return ast.Call(
            func=ast.Name(id="MinDistanceFrom", ctx=loadCtx),
            args=[self.visit(node.target)],
            keywords=(
                [ast.keyword(arg="Y", value=self.visit(node.base))]
                if node.base is not None
                else []
            ),
        )

    def visit_DistancePastOp(self, node: s.DistancePastOp):
        return ast.Call(
            func=ast.Name(id="DistancePast", ctx=loadCtx),
            args=[self.visit(node.target)],
            keywords=(
                []
                if node.base is None
                else [ast.keyword(arg="Y", value=self.visit(node.base))]
            ),
        )

    def visit_AngleFromOp(self, node: s.AngleFromOp):
        assert (
            node.base is not None or node.target is not None
        ), "neither target nor base were specified in AngleFromOp"
        keywords = []
        if node.base is not None:
            keywords.append(ast.keyword("X", self.visit(node.base)))
        if node.target is not None:
            keywords.append(ast.keyword("Y", self.visit(node.target)))
        return ast.Call(
            func=ast.Name(id="AngleFrom", ctx=loadCtx),
            args=[],
            keywords=keywords,
        )

    def visit_AltitudeFromOp(self, node: s.AltitudeFromOp):
        assert (
            node.base is not None or node.target is not None
        ), "neither target nor base were specified in AltitudeFromOp"
        keywords = []
        if node.base is not None:
            keywords.append(ast.keyword("X", self.visit(node.base)))
        if node.target is not None:
            keywords.append(ast.keyword("Y", self.visit(node.target)))
        return ast.Call(
            func=ast.Name(id="AltitudeFrom", ctx=loadCtx),
            args=[],
            keywords=keywords,
        )

    def visit_FollowOp(self, node: s.FollowOp):
        return ast.Call(
            func=ast.Name(id="Follow", ctx=loadCtx),
            args=[
                self.visit(node.target),
                self.visit(node.base),
                self.visit(node.distance),
            ],
            keywords=[],
        )

    def visit_VisibleOp(self, node: s.VisibleOp):
        return ast.Call(
            func=ast.Name(id="Visible", ctx=loadCtx),
            args=[self.visit(node.region)],
            keywords=[],
        )

    def visit_NotVisibleOp(self, node: s.VisibleOp):
        return ast.Call(
            func=ast.Name(id="NotVisible", ctx=loadCtx),
            args=[self.visit(node.region)],
            keywords=[],
        )

    def visit_VisibleFromOp(self, node: s.VisibleFromOp):
        return ast.Call(
            func=ast.Name(id="VisibleFromOp", ctx=loadCtx),
            args=[self.visit(node.region), self.visit(node.base)],
            keywords=[],
        )

    def visit_NotVisibleFromOp(self, node: s.VisibleFromOp):
        return ast.Call(
            func=ast.Name(id="NotVisibleFromOp", ctx=loadCtx),
            args=[self.visit(node.region), self.visit(node.base)],
            keywords=[],
        )

    def visit_PositionOfOp(self, node: s.PositionOfOp):
        return ast.Call(
            func=ast.Name(id=node.position.functionName, ctx=loadCtx),
            args=[self.visit(node.target)],
            keywords=[],
        )

    def visit_DegOp(self, node: s.DegOp):
        return ast.BinOp(
            left=self.visit(node.operand),
            op=ast.Mult(),
            right=ast.Constant(0.017453292519943295),
        )

    def visit_VectorOp(self, node: s.VectorOp):
        return ast.Call(
            func=ast.Name(id="Vector", ctx=loadCtx),
            args=[self.visit(node.left), self.visit(node.right)],
            keywords=[],
        )

    def visit_FieldAtOp(self, node: s.FieldAtOp):
        return ast.Call(
            func=ast.Name(id="FieldAt", ctx=loadCtx),
            args=[self.visit(node.left), self.visit(node.right)],
            keywords=[],
        )

    def visit_RelativeToOp(self, node: s.RelativeToOp):
        return ast.Call(
            func=ast.Name(id="RelativeTo", ctx=loadCtx),
            args=[self.visit(node.left), self.visit(node.right)],
            keywords=[],
        )

    def visit_OffsetAlongOp(self, node: s.OffsetAlongOp):
        return ast.Call(
            func=ast.Name(id="OffsetAlong", ctx=loadCtx),
            args=[
                self.visit(node.base),
                self.visit(node.direction),
                self.visit(node.offset),
            ],
            keywords=[],
        )

    def visit_CanSeeOp(self, node: s.CanSeeOp):
        return ast.Call(
            func=ast.Name(id="CanSee", ctx=loadCtx),
            args=[
                self.visit(node.left),
                self.visit(node.right),
            ],
            keywords=[],
        )

    def visit_IntersectsOp(self, node: s.IntersectsOp):
        return ast.Call(
            func=ast.Name(id="Intersects", ctx=loadCtx),
            args=[
                self.visit(node.left),
                self.visit(node.right),
            ],
            keywords=[],
        )
