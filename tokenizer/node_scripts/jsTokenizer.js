/**
 * Node script that reads JavaScript source code from stdin, and outputs tokens and indexes of the source code to stdout.
 * The source code is tokenized with Esprima 4: https://github.com/jquery/esprima/releases/tag/4.0.0.
 *
 * Token types are from:
 * https://github.com/jquery/esprima/blob/ea90f4a93c0f8bfb19c1f101bf19c1ea97a52e6a/src/token.ts
 *
 * Unknown token types will be given the name 'js-unknown', otherwise 'js-' appended with the esprima token type.
 */

"use strict";

const fs = require('fs');
const esprima = require('esprima');

const esprimaTokens = new Set([
  "Boolean",
  "<end>",
  "Identifier",
  "Keyword",
  "Null",
  "Numeric",
  "Punctuator",
  "String",
  "RegularExpression",
  "Template",
]);

// Return an Array from iterable, with each string in iterable prefixed with "js-"
function jsPrefixed(iterable) {
  return Array.from(iterable, s => "js-" + s);
}

function tokenize(source, validTokens) {
  let tokens = [];
  let indexes = [];
  esprima.tokenize(source, { range: true }).forEach(token => {
    const tokenName = (!validTokens.has(token.type)) ? "unknown" : token.type;
    tokens.push(tokenName);
    indexes.push(token.range);
  });
  return {tokens: jsPrefixed(tokens), indexes: indexes};
};

function main() {
  const source = fs.readFileSync("/dev/stdin").toString();
  const tokenizedData = tokenize(source, esprimaTokens);
  if (!tokenizedData.hasOwnProperty("tokens") ||
      !tokenizedData.hasOwnProperty("indexes")) {
    process.exit(1);
  }
  return JSON.stringify(tokenizedData);
};


if (require.main === module) {
  console.log(main());
}

module.exports = {
  tokenize: tokenize,
  tokenTypes: jsPrefixed(esprimaTokens)
};
