from pygments.lexers.c_cpp import CFamilyLexer

src = '''#include <stdio.h>
#include <string.h>

void print_random_number() {
    printf("Random number: %d\n", rand());
}

int main() {
    print_random_number();
    return 0;
}'''

#Get tokens
lexer = CFamilyLexer()
tokens = lexer.get_tokens_unprocessed(src)

#Print tokens
for token in tokens:
    print(str(token[1]).replace('.', '_').upper(), token[2], f'[{token[0], token[0] + len(token[2])}]')
