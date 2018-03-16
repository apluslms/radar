/**
 * Node script that reads CSS source code from stdin, and outputs tokens and indexes of the source code to stdout.
 * Input is parsed with the CSS parser used by csslint.net:
 * https://github.com/CSSLint/parser-lib/tree/v1.1.1
 *
 */

"use strict";

const fs = require('fs');
const parserlib = require('parserlib');

const tokenMap = {
  'property': '0',
  'selector': '1',
  'startrule': '2',
  'startmedia': '3',
  'media': '4',
  'startfontface': '5',
  'startpagemargin': '6',
  'startkeyframes': '7',
  'namespace': '8',
};

// > accumulate([1, 2, 3, 4])
// [ 1, 3, 6, 10 ]
function accumulate(arr) {
  return arr.reduce((xs, x) => (xs.length > 0) ? xs.concat(xs[xs.length-1] + x) : [x], []);
};


function tokenize(source, tokenMap) {
  const sourceLines = source.split(/\r\n|\r|\n/);
  const lineLengths = sourceLines.map(line => line.length + 1); // chars + 1 newline
  const indexOffsets = accumulate(lineLengths);
  function rowColPosToIndex(row, col) {
    return ((row > 1) ? indexOffsets[row-2] : 0) + col - 1;
  };

  let tokens = [];
  let indexes = [];
  const parser = new parserlib.css.Parser();
  const tokenTypes = Object.keys(tokenMap);
  tokenTypes.forEach(tokenType => {
    let listener = "none";
    if (tokenType === "startrule") {
      listener = event => {
        event.selectors.forEach(s => {
          tokens.push(tokenMap["selector"]);
          indexes.push([rowColPosToIndex(s.line, s.col),
                        rowColPosToIndex(s.line, s.col + s.text.length)]);
        });
      };
    } else if (tokenType === "property") {
      listener = event => {
        tokens.push(tokenMap[event.type]);
        indexes.push([rowColPosToIndex(event.line, event.col),
                      rowColPosToIndex(event.line, event.col + event.property.text.length)]);
      };
    } else if (tokenType === "startmedia") {
      listener = event => {
        event.media.forEach(m => {
          tokens.push(tokenMap["media"]);
          indexes.push([rowColPosToIndex(m.line, m.col),
                        rowColPosToIndex(m.line, m.col + m.text.length)]);
        });
      };
    } else if (tokenMap.hasOwnProperty(tokenType)) {
      listener = event => {
        if (typeof event.text !== "undefined") {
          tokens.push(tokenMap[event.type]);
          indexes.push([rowColPosToIndex(event.line, event.col),
                        rowColPosToIndex(event.line, event.col + event.text.length)]);
        }
      };
    }
    if (listener !== "none") {
      parser.addListener(tokenType, listener);
    }
  });

  parser.parse(source);

  return {tokens: tokens.join(''), indexes: indexes};
};

function main() {
  const source = fs.readFileSync("/dev/stdin").toString();
  const tokenizedData = tokenize(source, tokenMap);
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
  tokenMap: tokenMap
};
