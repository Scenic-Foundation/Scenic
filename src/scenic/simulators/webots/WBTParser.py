# Generated from WBT.g4 by ANTLR 4.13.1
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,16,121,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,1,0,1,0,1,0,5,0,28,
        8,0,10,0,12,0,31,9,0,1,1,1,1,1,1,4,1,36,8,1,11,1,12,1,37,1,2,1,2,
        1,2,1,2,1,3,1,3,1,3,1,3,1,3,1,3,3,3,50,8,3,1,4,1,4,1,4,5,4,55,8,
        4,10,4,12,4,58,9,4,1,5,1,5,1,5,1,5,1,5,3,5,65,8,5,1,6,1,6,1,6,1,
        6,1,6,3,6,72,8,6,1,7,4,7,75,8,7,11,7,12,7,76,1,8,1,8,1,9,1,9,1,9,
        5,9,84,8,9,10,9,12,9,87,9,9,1,9,3,9,90,8,9,1,9,1,9,1,9,1,9,1,9,4,
        9,97,8,9,11,9,12,9,98,1,9,3,9,102,8,9,1,9,1,9,3,9,106,8,9,1,10,3,
        10,109,8,10,1,10,1,10,3,10,113,8,10,4,10,115,8,10,11,10,12,10,116,
        1,11,1,11,1,11,0,0,12,0,2,4,6,8,10,12,14,16,18,20,22,0,1,1,0,9,10,
        128,0,29,1,0,0,0,2,32,1,0,0,0,4,39,1,0,0,0,6,43,1,0,0,0,8,56,1,0,
        0,0,10,64,1,0,0,0,12,71,1,0,0,0,14,74,1,0,0,0,16,78,1,0,0,0,18,105,
        1,0,0,0,20,114,1,0,0,0,22,118,1,0,0,0,24,28,3,2,1,0,25,28,3,6,3,
        0,26,28,3,4,2,0,27,24,1,0,0,0,27,25,1,0,0,0,27,26,1,0,0,0,28,31,
        1,0,0,0,29,27,1,0,0,0,29,30,1,0,0,0,30,1,1,0,0,0,31,29,1,0,0,0,32,
        33,5,1,0,0,33,35,5,15,0,0,34,36,5,16,0,0,35,34,1,0,0,0,36,37,1,0,
        0,0,37,35,1,0,0,0,37,38,1,0,0,0,38,3,1,0,0,0,39,40,5,2,0,0,40,41,
        5,13,0,0,41,42,3,6,3,0,42,5,1,0,0,0,43,44,5,13,0,0,44,45,5,3,0,0,
        45,46,5,16,0,0,46,47,3,8,4,0,47,49,5,4,0,0,48,50,5,16,0,0,49,48,
        1,0,0,0,49,50,1,0,0,0,50,7,1,0,0,0,51,52,3,10,5,0,52,53,5,16,0,0,
        53,55,1,0,0,0,54,51,1,0,0,0,55,58,1,0,0,0,56,54,1,0,0,0,56,57,1,
        0,0,0,57,9,1,0,0,0,58,56,1,0,0,0,59,60,5,5,0,0,60,61,5,13,0,0,61,
        65,3,12,6,0,62,63,5,13,0,0,63,65,3,12,6,0,64,59,1,0,0,0,64,62,1,
        0,0,0,65,11,1,0,0,0,66,72,3,14,7,0,67,72,3,16,8,0,68,72,3,18,9,0,
        69,72,3,6,3,0,70,72,3,22,11,0,71,66,1,0,0,0,71,67,1,0,0,0,71,68,
        1,0,0,0,71,69,1,0,0,0,71,70,1,0,0,0,72,13,1,0,0,0,73,75,5,14,0,0,
        74,73,1,0,0,0,75,76,1,0,0,0,76,74,1,0,0,0,76,77,1,0,0,0,77,15,1,
        0,0,0,78,79,5,15,0,0,79,17,1,0,0,0,80,85,5,6,0,0,81,82,5,16,0,0,
        82,84,3,12,6,0,83,81,1,0,0,0,84,87,1,0,0,0,85,83,1,0,0,0,85,86,1,
        0,0,0,86,89,1,0,0,0,87,85,1,0,0,0,88,90,5,16,0,0,89,88,1,0,0,0,89,
        90,1,0,0,0,90,91,1,0,0,0,91,106,5,7,0,0,92,93,5,6,0,0,93,96,3,20,
        10,0,94,95,5,8,0,0,95,97,3,20,10,0,96,94,1,0,0,0,97,98,1,0,0,0,98,
        96,1,0,0,0,98,99,1,0,0,0,99,101,1,0,0,0,100,102,5,8,0,0,101,100,
        1,0,0,0,101,102,1,0,0,0,102,103,1,0,0,0,103,104,5,7,0,0,104,106,
        1,0,0,0,105,80,1,0,0,0,105,92,1,0,0,0,106,19,1,0,0,0,107,109,5,16,
        0,0,108,107,1,0,0,0,108,109,1,0,0,0,109,110,1,0,0,0,110,112,5,14,
        0,0,111,113,5,16,0,0,112,111,1,0,0,0,112,113,1,0,0,0,113,115,1,0,
        0,0,114,108,1,0,0,0,115,116,1,0,0,0,116,114,1,0,0,0,116,117,1,0,
        0,0,117,21,1,0,0,0,118,119,7,0,0,0,119,23,1,0,0,0,16,27,29,37,49,
        56,64,71,76,85,89,98,101,105,108,112,116
    ]

class WBTParser ( Parser ):

    grammarFileName = "WBT.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'EXTERNPROTO'", "'DEF'", "' {'", "'}'", 
                     "'hidden'", "'['", "']'", "','", "'TRUE'", "'FALSE'" ]

    symbolicNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "Comment", 
                      "Whitespace", "Identifier", "Number", "String", "Newline" ]

    RULE_world = 0
    RULE_externproto = 1
    RULE_defn = 2
    RULE_node = 3
    RULE_nodeBody = 4
    RULE_attribute = 5
    RULE_value = 6
    RULE_vector = 7
    RULE_string = 8
    RULE_array = 9
    RULE_vectorWithNewlines = 10
    RULE_boolean = 11

    ruleNames =  [ "world", "externproto", "defn", "node", "nodeBody", "attribute", 
                   "value", "vector", "string", "array", "vectorWithNewlines", 
                   "boolean" ]

    EOF = Token.EOF
    T__0=1
    T__1=2
    T__2=3
    T__3=4
    T__4=5
    T__5=6
    T__6=7
    T__7=8
    T__8=9
    T__9=10
    Comment=11
    Whitespace=12
    Identifier=13
    Number=14
    String=15
    Newline=16

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.1")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class WorldContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def externproto(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(WBTParser.ExternprotoContext)
            else:
                return self.getTypedRuleContext(WBTParser.ExternprotoContext,i)


        def node(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(WBTParser.NodeContext)
            else:
                return self.getTypedRuleContext(WBTParser.NodeContext,i)


        def defn(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(WBTParser.DefnContext)
            else:
                return self.getTypedRuleContext(WBTParser.DefnContext,i)


        def getRuleIndex(self):
            return WBTParser.RULE_world

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitWorld" ):
                return visitor.visitWorld(self)
            else:
                return visitor.visitChildren(self)




    def world(self):

        localctx = WBTParser.WorldContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_world)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 29
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 8198) != 0):
                self.state = 27
                self._errHandler.sync(self)
                token = self._input.LA(1)
                if token in [1]:
                    self.state = 24
                    self.externproto()
                    pass
                elif token in [13]:
                    self.state = 25
                    self.node()
                    pass
                elif token in [2]:
                    self.state = 26
                    self.defn()
                    pass
                else:
                    raise NoViableAltException(self)

                self.state = 31
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExternprotoContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def String(self):
            return self.getToken(WBTParser.String, 0)

        def Newline(self, i:int=None):
            if i is None:
                return self.getTokens(WBTParser.Newline)
            else:
                return self.getToken(WBTParser.Newline, i)

        def getRuleIndex(self):
            return WBTParser.RULE_externproto

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExternproto" ):
                return visitor.visitExternproto(self)
            else:
                return visitor.visitChildren(self)




    def externproto(self):

        localctx = WBTParser.ExternprotoContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_externproto)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 32
            self.match(WBTParser.T__0)
            self.state = 33
            self.match(WBTParser.String)
            self.state = 35 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 34
                self.match(WBTParser.Newline)
                self.state = 37 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==16):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class DefnContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def Identifier(self):
            return self.getToken(WBTParser.Identifier, 0)

        def node(self):
            return self.getTypedRuleContext(WBTParser.NodeContext,0)


        def getRuleIndex(self):
            return WBTParser.RULE_defn

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDefn" ):
                return visitor.visitDefn(self)
            else:
                return visitor.visitChildren(self)




    def defn(self):

        localctx = WBTParser.DefnContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_defn)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 39
            self.match(WBTParser.T__1)
            self.state = 40
            self.match(WBTParser.Identifier)
            self.state = 41
            self.node()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class NodeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def Identifier(self):
            return self.getToken(WBTParser.Identifier, 0)

        def Newline(self, i:int=None):
            if i is None:
                return self.getTokens(WBTParser.Newline)
            else:
                return self.getToken(WBTParser.Newline, i)

        def nodeBody(self):
            return self.getTypedRuleContext(WBTParser.NodeBodyContext,0)


        def getRuleIndex(self):
            return WBTParser.RULE_node

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitNode" ):
                return visitor.visitNode(self)
            else:
                return visitor.visitChildren(self)




    def node(self):

        localctx = WBTParser.NodeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_node)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 43
            self.match(WBTParser.Identifier)
            self.state = 44
            self.match(WBTParser.T__2)
            self.state = 45
            self.match(WBTParser.Newline)
            self.state = 46
            self.nodeBody()
            self.state = 47
            self.match(WBTParser.T__3)
            self.state = 49
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,3,self._ctx)
            if la_ == 1:
                self.state = 48
                self.match(WBTParser.Newline)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class NodeBodyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def attribute(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(WBTParser.AttributeContext)
            else:
                return self.getTypedRuleContext(WBTParser.AttributeContext,i)


        def Newline(self, i:int=None):
            if i is None:
                return self.getTokens(WBTParser.Newline)
            else:
                return self.getToken(WBTParser.Newline, i)

        def getRuleIndex(self):
            return WBTParser.RULE_nodeBody

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitNodeBody" ):
                return visitor.visitNodeBody(self)
            else:
                return visitor.visitChildren(self)




    def nodeBody(self):

        localctx = WBTParser.NodeBodyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_nodeBody)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 56
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==5 or _la==13:
                self.state = 51
                self.attribute()
                self.state = 52
                self.match(WBTParser.Newline)
                self.state = 58
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AttributeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def Identifier(self):
            return self.getToken(WBTParser.Identifier, 0)

        def value(self):
            return self.getTypedRuleContext(WBTParser.ValueContext,0)


        def getRuleIndex(self):
            return WBTParser.RULE_attribute

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAttribute" ):
                return visitor.visitAttribute(self)
            else:
                return visitor.visitChildren(self)




    def attribute(self):

        localctx = WBTParser.AttributeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_attribute)
        try:
            self.state = 64
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [5]:
                self.enterOuterAlt(localctx, 1)
                self.state = 59
                self.match(WBTParser.T__4)
                self.state = 60
                self.match(WBTParser.Identifier)
                self.state = 61
                self.value()
                pass
            elif token in [13]:
                self.enterOuterAlt(localctx, 2)
                self.state = 62
                self.match(WBTParser.Identifier)
                self.state = 63
                self.value()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ValueContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def vector(self):
            return self.getTypedRuleContext(WBTParser.VectorContext,0)


        def string(self):
            return self.getTypedRuleContext(WBTParser.StringContext,0)


        def array(self):
            return self.getTypedRuleContext(WBTParser.ArrayContext,0)


        def node(self):
            return self.getTypedRuleContext(WBTParser.NodeContext,0)


        def boolean(self):
            return self.getTypedRuleContext(WBTParser.BooleanContext,0)


        def getRuleIndex(self):
            return WBTParser.RULE_value

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitValue" ):
                return visitor.visitValue(self)
            else:
                return visitor.visitChildren(self)




    def value(self):

        localctx = WBTParser.ValueContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_value)
        try:
            self.state = 71
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [14]:
                self.enterOuterAlt(localctx, 1)
                self.state = 66
                self.vector()
                pass
            elif token in [15]:
                self.enterOuterAlt(localctx, 2)
                self.state = 67
                self.string()
                pass
            elif token in [6]:
                self.enterOuterAlt(localctx, 3)
                self.state = 68
                self.array()
                pass
            elif token in [13]:
                self.enterOuterAlt(localctx, 4)
                self.state = 69
                self.node()
                pass
            elif token in [9, 10]:
                self.enterOuterAlt(localctx, 5)
                self.state = 70
                self.boolean()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class VectorContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def Number(self, i:int=None):
            if i is None:
                return self.getTokens(WBTParser.Number)
            else:
                return self.getToken(WBTParser.Number, i)

        def getRuleIndex(self):
            return WBTParser.RULE_vector

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitVector" ):
                return visitor.visitVector(self)
            else:
                return visitor.visitChildren(self)




    def vector(self):

        localctx = WBTParser.VectorContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_vector)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 74 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 73
                self.match(WBTParser.Number)
                self.state = 76 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==14):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StringContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def String(self):
            return self.getToken(WBTParser.String, 0)

        def getRuleIndex(self):
            return WBTParser.RULE_string

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitString" ):
                return visitor.visitString(self)
            else:
                return visitor.visitChildren(self)




    def string(self):

        localctx = WBTParser.StringContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_string)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 78
            self.match(WBTParser.String)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ArrayContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def Newline(self, i:int=None):
            if i is None:
                return self.getTokens(WBTParser.Newline)
            else:
                return self.getToken(WBTParser.Newline, i)

        def value(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(WBTParser.ValueContext)
            else:
                return self.getTypedRuleContext(WBTParser.ValueContext,i)


        def vectorWithNewlines(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(WBTParser.VectorWithNewlinesContext)
            else:
                return self.getTypedRuleContext(WBTParser.VectorWithNewlinesContext,i)


        def getRuleIndex(self):
            return WBTParser.RULE_array

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArray" ):
                return visitor.visitArray(self)
            else:
                return visitor.visitChildren(self)




    def array(self):

        localctx = WBTParser.ArrayContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_array)
        self._la = 0 # Token type
        try:
            self.state = 105
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,12,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 80
                self.match(WBTParser.T__5)
                self.state = 85
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,8,self._ctx)
                while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                    if _alt==1:
                        self.state = 81
                        self.match(WBTParser.Newline)
                        self.state = 82
                        self.value() 
                    self.state = 87
                    self._errHandler.sync(self)
                    _alt = self._interp.adaptivePredict(self._input,8,self._ctx)

                self.state = 89
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==16:
                    self.state = 88
                    self.match(WBTParser.Newline)


                self.state = 91
                self.match(WBTParser.T__6)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 92
                self.match(WBTParser.T__5)
                self.state = 93
                self.vectorWithNewlines()
                self.state = 96 
                self._errHandler.sync(self)
                _alt = 1
                while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                    if _alt == 1:
                        self.state = 94
                        self.match(WBTParser.T__7)
                        self.state = 95
                        self.vectorWithNewlines()

                    else:
                        raise NoViableAltException(self)
                    self.state = 98 
                    self._errHandler.sync(self)
                    _alt = self._interp.adaptivePredict(self._input,10,self._ctx)

                self.state = 101
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==8:
                    self.state = 100
                    self.match(WBTParser.T__7)


                self.state = 103
                self.match(WBTParser.T__6)
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class VectorWithNewlinesContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def Number(self, i:int=None):
            if i is None:
                return self.getTokens(WBTParser.Number)
            else:
                return self.getToken(WBTParser.Number, i)

        def Newline(self, i:int=None):
            if i is None:
                return self.getTokens(WBTParser.Newline)
            else:
                return self.getToken(WBTParser.Newline, i)

        def getRuleIndex(self):
            return WBTParser.RULE_vectorWithNewlines

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitVectorWithNewlines" ):
                return visitor.visitVectorWithNewlines(self)
            else:
                return visitor.visitChildren(self)




    def vectorWithNewlines(self):

        localctx = WBTParser.VectorWithNewlinesContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_vectorWithNewlines)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 114 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 108
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==16:
                    self.state = 107
                    self.match(WBTParser.Newline)


                self.state = 110
                self.match(WBTParser.Number)
                self.state = 112
                self._errHandler.sync(self)
                la_ = self._interp.adaptivePredict(self._input,14,self._ctx)
                if la_ == 1:
                    self.state = 111
                    self.match(WBTParser.Newline)


                self.state = 116 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==14 or _la==16):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BooleanContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser


        def getRuleIndex(self):
            return WBTParser.RULE_boolean

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBoolean" ):
                return visitor.visitBoolean(self)
            else:
                return visitor.visitChildren(self)




    def boolean(self):

        localctx = WBTParser.BooleanContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_boolean)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 118
            _la = self._input.LA(1)
            if not(_la==9 or _la==10):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





