
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

  //TODO use Tokens.BLA
  val typeMap = Map(
    TokenType("PACKAGE") -> '0',
    TokenType("STAR") -> '1',
    TokenType("WHILE") -> '2',
    TokenType("CASE") -> '3',
    TokenType("NEW") -> '4',
    TokenType("DO") -> '5',
    TokenType("EQUALS") -> '6',
    TokenType("SUBTYPE") -> '7',
    TokenType("SEALED") -> '9',
    TokenType("TYPE") -> 'a',
    TokenType("LBRACKET") -> 'b',
    TokenType("FINAL") -> 'c',
    TokenType("RPAREN") -> 'd',
    TokenType("IMPORT") -> 'e',
    TokenType("STRING_LITERAL") -> 'f',
    TokenType("STRING_PART") -> 'g',
    TokenType("FLOATING_POINT_LITERAL") -> 'h',
    TokenType("EXCLAMATION") -> 'i',
    TokenType("NEWLINES") -> 'j',
    TokenType("THIS") -> 'k',
    TokenType("RETURN") -> 'l',
    TokenType("VAL") -> 'm',
    TokenType("VAR") -> 'n',
    TokenType("SUPER") -> 'o',
    TokenType("RBRACE") -> 'p',
    TokenType("PRIVATE") -> 'q',
    TokenType("NULL") -> 'r',
    TokenType("ELSE") -> 's',
    TokenType("CHARACTER_LITERAL") -> 't',
    TokenType("MATCH") -> 'u',
    TokenType("TRY") -> 'v',
    TokenType("WS") -> 'x',
    TokenType("SUPERTYPE") -> 'y',
    TokenType("INTEGER_LITERAL") -> 'z',
    TokenType("OP") -> 'A',
    TokenType("USCORE") -> 'B',
    TokenType("LOWER") -> 'C',
    TokenType("CATCH") -> 'D',
    TokenType("FALSE") -> 'E',
    TokenType("VARID") -> 'F',
    TokenType("THROW") -> 'G',
    TokenType("UPPER") -> 'H',
    TokenType("PROTECTED") -> 'I',
    TokenType("CLASS") -> 'J',
    TokenType("DEF") -> 'K',
    TokenType("LBRACE") -> 'L',
    TokenType("FOR") -> 'M',
    TokenType("LARROW") -> 'N',
    TokenType("ABSTRACT") -> 'O',
    TokenType("LPAREN") -> 'P',
    TokenType("IF") -> 'Q',
    TokenType("AT") -> 'R',
    TokenType("SYMBOL_LITERAL") -> 'S',
    TokenType("OBJECT") -> 'T',
    TokenType("COMMA") -> 'U',
    TokenType("YIELD") -> 'V',
    TokenType("TILDE") -> 'X',
    TokenType("PLUS") -> 'Y',
    TokenType("PIPE") -> 'Z',
    TokenType("VIEWBOUND") -> '!',
    TokenType("RBRACKET") -> '"',
    TokenType("DOT") -> '#',
    TokenType("WITH") -> '$',
    TokenType("IMPLICIT") -> '%',
    TokenType("LAZY") -> '&',
    TokenType("TRAIT") -> '(',
    TokenType("HASH") -> ')',
    TokenType("FORSOME") -> '*',
    TokenType("MINUS") -> '+',
    TokenType("TRUE") -> ',',
    TokenType("SEMI") -> '-',
    TokenType("COLON") -> '.',
    TokenType("OTHERID") -> '/',
    TokenType("FINALLY") -> ':',
    TokenType("OVERRIDE") -> ';',
    TokenType("ARROW") -> '<',
    TokenType("EXTENDS") -> '=',
    TokenType("INTERPOLATION_ID") -> '>',
    TokenType("XML_START_OPEN", isXml = true) -> '\\',
    TokenType("XML_EMPTY_CLOSE", isXml = true) -> '@',
    TokenType("XML_TAG_CLOSE", isXml = true) -> '[',
    TokenType("XML_END_OPEN", isXml = true) -> ']',
    TokenType("XML_WHITESPACE", isXml = true) -> '^',
    TokenType("XML_ATTR_EQ", isXml = true) -> '_',
    TokenType("XML_ATTR_VALUE", isXml = true) -> '`',
    TokenType("XML_NAME", isXml = true) -> '{',
    TokenType("XML_PCDATA", isXml = true) -> '|',
    TokenType("XML_CDATA", isXml = true) -> '}',
    TokenType("XML_UNPARSED", isXml = true) -> '8',
    TokenType("XML_PROCESSING_INSTRUCTION", isXml = true) -> '~')

  val source = io.Source.stdin.getLines.mkString("\n")
  val tokens = ScalaLexer.tokenise(source, scalaVersion = ScalaVersions.DEFAULT_VERSION)
  val filtered = tokens.filter(t => !t.tokenType.isComment && !t.tokenType.isNewline && t.tokenType != Tokens.EOF)

  val ids = filtered.map(t => typeMap.getOrElse(t.tokenType, '?'))
  val chars = filtered.map(t => t.offset + "-" + t.lastCharacterOffset)

  println(ids.mkString(""))
  println(chars.mkString(","))
}
