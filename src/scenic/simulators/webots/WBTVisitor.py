# Generated from WBT.g4 by ANTLR 4.13.1
from antlr4 import *
if "." in __name__:
    from .WBTParser import WBTParser
else:
    from WBTParser import WBTParser

# This class defines a complete generic visitor for a parse tree produced by WBTParser.

class WBTVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by WBTParser#world.
    def visitWorld(self, ctx:WBTParser.WorldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by WBTParser#externproto.
    def visitExternproto(self, ctx:WBTParser.ExternprotoContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by WBTParser#defn.
    def visitDefn(self, ctx:WBTParser.DefnContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by WBTParser#node.
    def visitNode(self, ctx:WBTParser.NodeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by WBTParser#nodeBody.
    def visitNodeBody(self, ctx:WBTParser.NodeBodyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by WBTParser#attribute.
    def visitAttribute(self, ctx:WBTParser.AttributeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by WBTParser#value.
    def visitValue(self, ctx:WBTParser.ValueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by WBTParser#vector.
    def visitVector(self, ctx:WBTParser.VectorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by WBTParser#string.
    def visitString(self, ctx:WBTParser.StringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by WBTParser#array.
    def visitArray(self, ctx:WBTParser.ArrayContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by WBTParser#vectorWithNewlines.
    def visitVectorWithNewlines(self, ctx:WBTParser.VectorWithNewlinesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by WBTParser#boolean.
    def visitBoolean(self, ctx:WBTParser.BooleanContext):
        return self.visitChildren(ctx)



del WBTParser