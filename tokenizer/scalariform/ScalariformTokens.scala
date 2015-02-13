
import scalariform.ScalaVersions
import scalariform.lexer.ScalaLexer
import scalariform.lexer.Token
import scalariform.lexer.TokenType
import scalariform.lexer.Tokens
import scala.collection.mutable.Buffer
import scala.collection.mutable.HashMap

/**
 * Tokenizes scala source using scalariform lexer.
 */
object ScalariformTokens extends App {

  val typeMap = Map(

    Tokens.ABSTRACT -> 'A',
    Tokens.PROTECTED -> 'B',
    Tokens.CLASS -> 'C',
    Tokens.DEF -> 'D',
    Tokens.EXTENDS -> 'E',
    Tokens.FINAL -> 'F',
    Tokens.PRIVATE -> 'H',
    Tokens.IMPORT -> 'I',
    Tokens.IMPLICIT -> 'J',
    Tokens.SEALED -> 'L',
    Tokens.NEW -> 'N',
    Tokens.OBJECT -> 'O',
    Tokens.PACKAGE -> 'P',
    Tokens.RETURN -> 'R',
    Tokens.SUBTYPE -> 'S',
    Tokens.TRAIT -> 'T',
    Tokens.SUPERTYPE -> 'U',
    Tokens.OVERRIDE -> 'V',
    Tokens.WITH -> 'W',
    Tokens.WS -> 'X',
    Tokens.TYPE -> 'Y',
    Tokens.LAZY -> 'Z',

    Tokens.VARID -> 'a',
    Tokens.SYMBOL_LITERAL -> 'b',
    Tokens.CHARACTER_LITERAL -> 'c',
    Tokens.FLOATING_POINT_LITERAL -> 'd',
    Tokens.CASE -> 'e',
    Tokens.FOR -> 'f',
    Tokens.FORSOME -> 'g',
    Tokens.SEMI -> 'h',
    Tokens.INTEGER_LITERAL -> 'i',
    Tokens.YIELD -> 'l',
    Tokens.MATCH -> 'm',
    Tokens.NULL -> 'n',
    Tokens.DO -> 'o',
    Tokens.STRING_PART -> 'p',
    Tokens.THROW -> 'q',
    Tokens.VAR -> 'r',
    Tokens.STRING_LITERAL -> 's',
    Tokens.THIS -> 't',
    Tokens.SUPER -> 'u',
    Tokens.VAL -> 'v',
    Tokens.WHILE -> 'w',
    Tokens.CATCH -> 'x',
    Tokens.TRY -> 'y',
    Tokens.FINALLY -> 'z',

    Tokens.IF -> '?',
    Tokens.ELSE -> '/',
    Tokens.OP -> '%',
    Tokens.FALSE -> '0',
    Tokens.TRUE -> '1',

    Tokens.STAR -> '*',
    Tokens.COMMA -> ',',
    Tokens.DOT -> '.',
    Tokens.COLON -> ':',
    Tokens.TILDE -> '~',
    Tokens.PLUS -> '+',
    Tokens.MINUS -> '-',
    Tokens.PIPE -> '|',
    Tokens.EXCLAMATION -> '!',
    Tokens.EQUALS -> '=',
    Tokens.AT -> '@',
    Tokens.HASH -> '#',
    Tokens.LPAREN -> '(',
    Tokens.RPAREN -> ')',    
    Tokens.LBRACKET -> '[',
    Tokens.RBRACKET -> ']',
    Tokens.LBRACE -> '{',
    Tokens.RBRACE -> '}',
    Tokens.LARROW -> '<',
    Tokens.ARROW -> '>',
    Tokens.LOWER -> '_',
    Tokens.UPPER -> '^',

    Tokens.USCORE -> '6',
    Tokens.VIEWBOUND -> '7',
    Tokens.INTERPOLATION_ID -> '8',
    Tokens.OTHERID -> '9',

    Tokens.XML_START_OPEN -> '$',
    Tokens.XML_EMPTY_CLOSE -> '$',
    Tokens.XML_TAG_CLOSE -> '$',
    Tokens.XML_END_OPEN -> '$',
    Tokens.XML_WHITESPACE -> '$',
    Tokens.XML_ATTR_EQ -> '$',
    Tokens.XML_ATTR_VALUE -> '$',
    Tokens.XML_NAME -> '$',
    Tokens.XML_PCDATA -> '$',
    Tokens.XML_CDATA -> '$',
    Tokens.XML_UNPARSED -> '$',
    Tokens.XML_PROCESSING_INSTRUCTION -> '$')

  val source = io.Source.stdin.getLines.mkString("\n")
  val tokens = ScalaLexer.tokenise(source, scalaVersion = ScalaVersions.DEFAULT_VERSION)
  val filtered = tokens.filter(t => !t.tokenType.isComment && !t.tokenType.isNewline && t.tokenType != Tokens.EOF)

  val ids = filtered.map(t => typeMap.getOrElse(t.tokenType, '?'))
  val chars = filtered.map(t => t.offset + "-" + t.lastCharacterOffset)

  println(ids.mkString(""))
  println(chars.mkString(","))
}
