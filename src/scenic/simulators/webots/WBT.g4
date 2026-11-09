/* ANTLR 4 grammar for Webots world (.wbt) files.

   This is not a complete grammar, but seems to be adequate for the
   fragment used by the Webots OSM importer.

   To regenerate WBTLexer.py, WBTParser.py, and WBTVisitor.py, run
   ANTLR as follows:

   java -jar antlr.jar -no-listener -visitor -Dlanguage=Python3 WBT.g4
*/

grammar WBT;

world : (externproto | node | defn)* ;

externproto : 'EXTERNPROTO' String Newline+ ;

defn : 'DEF' Identifier node;

node : Identifier ' {' Newline nodeBody '}' Newline? ;

nodeBody : (attribute Newline)* ;

attribute
	: 'hidden' Identifier value
	| Identifier value ;

value : vector | string | array | node | boolean ;

vector : Number+ ;

string : String ;

/* The VRML grammar is highly ambiguous for multi-valued fields:
   we have no way of knowing whether whitespace (including newlines)
   separates two different values or components of a single value.
   The intended solution is to use type information about each field;
   instead, we use the following simple heuristic: vectors may be
   separated by commas, everything else only by newlines. This works
   for the two .wbt files I've looked at... */
array
	: '[' (Newline value)* Newline? ']'
	| '[' vectorWithNewlines (',' vectorWithNewlines)+ ','? ']' ;

vectorWithNewlines: (Newline? Number Newline?)+ ;

boolean : 'TRUE' | 'FALSE' ;

Comment : '#' .*? Newline+ -> skip ;

Whitespace : [ \t]+ -> skip ;

Identifier : Letter (Letter | Digit)* ;

fragment
Letter : [a-zA-Z_] ;

Number : '-'? Digit+ ('.' Digit+)? ('e' '-'? Digit+)? ;

fragment
Digit : [0-9] ;

String : '"' Character* '"' ;

fragment
Character : ~["\\] | '\\"' | '\\\\';

Newline : '\r'? '\n' ;
