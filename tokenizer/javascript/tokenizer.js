/**
 * Node script that reads JavaScript source code from stdin, and outputs tokens and indexes of the source code to stdout.
 * The source code is tokenized with Esprima 4: https://github.com/jquery/esprima/releases/tag/4.0.0.
 *
 * Esprima does not export a mapping from token names to integers.
 * Therefore, tokens have been mapped manually from the Esprima tokens enum:
 * https://github.com/jquery/esprima/blob/ea90f4a93c0f8bfb19c1f101bf19c1ea97a52e6a/src/token.ts
 */

"use strict";

const fs = require('fs');
const esprima = require('esprima');

const esprimaTokenMap = {
  "Boolean": "1",
  "<end>": "2",
  "Identifier": "3",
  "Keyword": "4",
  "Null": "5",
  "Numeric": "6",
  "Punctuator": "7",
  "String": "8",
  "RegularExpression": "9",
  "Template": "a"
};


const tokenize = function(source, tokenMap) {
  let tokens = [];
  let indexes = [];
  esprima.tokenize(source, { range: true }).forEach(token => {
    if (!tokenMap.hasOwnProperty(token.type)) {
      console.error("Found syntax token with no mapping. Token:");
      console.error(token);
      console.error("Not found in map:");
      console.error(tokenMap);
      return {};
    }
    tokens.push(tokenMap[token.type]);
    indexes.push(token.range);
  });
  return {tokens: tokens.join(''), indexes: indexes};
};

const main = function() {
  const source = fs.readFileSync("/dev/stdin").toString();
  const tokenizedData = tokenize(source, esprimaTokenMap);
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
  esprimaTokenMap: esprimaTokenMap
};
