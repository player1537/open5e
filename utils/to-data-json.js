#!/usr/bin/env node
'use strict';

const path = require('path');
const fs = require('fs');
const restructured = require('restructured').default /* exported as ES6 module */;
const assert = require('assert');

process.chdir(path.join(__dirname, '..'));

function parseSpellFile(filePath) {
  return new Promise((resolve, reject) => {
    fs.readFile(filePath, (err, contents) => {
      if (err) {
        return reject(err);
      }

      resolve(String(contents));
    })
  })
  .then(contents => restructured.parse(contents))
  .then(ast => {
    try {

      assert.equal('document', ast.type, `${filePath} doesn't contain a document`);
      assert.equal(2, ast.children.length, `${filePath} should contain two children`);

      const idComment = ast.children[0];
      assert.equal('comment', idComment.type, `${filePath}'s first child should be a comment`);
      assert.equal(1, idComment.children.length);
      assert.equal('text', idComment.children[0].type);
      const id = idComment.children[0].value.match(/^_srd:(.*):$/)[1];

      let section = ast.children[1];
      assert.equal('section', section.type, `${filePath}'s second child should be a section`);
      assert.equal(2, section.children.length, `${filePath}'s section should contain two children`);
      assert.equal('title', section.children[0].type, `${filePath}'s section's first child should be a title`);
      assert.equal('text', section.children[0].children[0].type, `${filePath}'s section's first child should be a title containing text`);
      const name = section.children[0].children[0].value;
      section = section.children[1];
      assert.equal('section', section.type, `${filePath}'s second child should contain a section`);
      assert.equal('title', section.children[0].type, `${filePath}'s section's first child should be a title`);
      assert.equal('text', section.children[0].children[0].type, `${filePath}'s section's first child should be a title containing text`);

      let level = '-1', school = '', ritual = false, match = section.children[0].children[0].value.match(/(.)(?:nd|st|rd|th)-level (.*?)( \(ritual\))?$/);
      if (match) {
        let _;
        [ _, level, school ] = match;
        ritual = match[3] != null;
      } else {
        match = section.children[0].children[0].value.match(/(.*) cantrip/);
        if (match) {
          level = '0';
          school = match[1].toLowerCase();
        }
      }

      level = +level;

      const spell = { id, name, level, school, ritual, description: [] };

      section.children.slice(1).forEach(child => {
        if (!child.children.length) {
          return;
        }

        const firstChild = child.children[0];
        const valueContainers = child.children;

        if (firstChild.type === 'strong') {
          assert.equal('paragraph', child.type, `${filePath}'s section contains a non-paragraph key/value pair`);
          const key = firstChild.children[0].value.toLowerCase().replace(/:$/, '');

          spell[key] = valuesToString(valueContainers.slice(1));
          return;
        }

        switch (child.type) {
          case 'paragraph':
            spell.description.push(valuesToString(valueContainers));
            break;
          case 'bullet_list':
            spell.description.push(
              valueContainers.map(value => {
                assert('list_item', value.type, `${filePath}: bullet_list contains non-list-item`);
                assert(1, value.children.length);
                value = value.children[0];
                assert('paragraph', value.type);
                
                return `- ${valuesToString(value.children)}`;
              }).join('\n')
            );
            break;
          case 'enumerated_list':
            spell.description.push(
              valueContainers.map((value, i) => {
                assert('list_item', value.type, `${filePath}: bullet_list contains non-list-item`);
                assert(1, value.children.length);
                value = value.children[0];
                assert('paragraph', value.type);
                
                return `${i}. ${valuesToString(value.children)}`;
              }).join('\n')
            );
            break;
          default:
            throw new Error(`Unsupported section child type: ${child.type}`);
        }
      });
      
      if (spell.duration){
        spell.concentration =  !! spell.duration.match(/Concentration, /)
        if (spell.concentration){
          spell.duration = spell.duration.slice(15);
        }
      }

      if (spell.components) {
        const M = spell.components.match(/M(?: \((.*)\))?$/);
        const components = {
          verbal: !! spell.components.match(/V(,|$)/),
          somatic: !! spell.components.match(/S(,|$)/),
          material: !!M && M[1]
        };

        spell.components = components;
      }
      
      if (spell.description) {
        let damageTypes = [];
        let damageRolls = [];
        let arrMatch = null;
        const damageValues = ['bludgeoning', 'piercing', 'slashing','fire','cold','psychic','poison','necrotic','radiant']
        const rePattern = /(\d+d\d+\+?\d?)?\s(\w+)\sdamage/ig;
        while (arrMatch = rePattern.exec(spell.description)){
          //if it is a type of damage and isn't in the results array already
          if (damageValues.indexOf(arrMatch[2]) > -1 && damageTypes.indexOf(arrMatch[2]) <= -1){
            damageTypes.push(arrMatch[2]);
          }
          if (arrMatch[1]){
            damageRolls.push(arrMatch[1]+" "+arrMatch[2])
          }
        }
        spell.damageTypes = damageTypes;
        spell.damageRolls = damageRolls;
      }

      return spell;

      function valuesToString(values) {
        return values.map(value => {
          switch(value.type) {
            case 'text':
              return value.value.replace(':ref:', '').trim();
            case 'emphasis':
            case 'strong':
              return valuesToString(value.children);
            case 'interpreted_text':
              return valuesToString(value.children).replace(/srd:/, '');
            default:
              throw new Error(`Invalid value type: ${value.type}`);
          }
        }).join(' ');
      }
    } catch (e) {
      console.log(e.stack);
      console.log(JSON.stringify(ast, null, 2));
      process.exit(1);
      throw e;
    }
  }, e => {
    // see https://github.com/seikichi/restructured/issues/2
    console.error(`RST parse error "${e && e.message}" for ${path.relative(process.cwd(), filePath)}`);
    return Promise.resolve(null);
  });
}

function parseLetterDirectory(letter, parentDirectory) {
  return new Promise((resolve, reject) => {
    fs.readdir(path.join(parentDirectory, letter), (err, files) => {
      if (err) {
        if (err.code === 'ENOENT') {
          return resolve([]);
        }

        return reject(err);
      }

      resolve(files.filter(file => file !== 'index.rst'));
    });
  })
  .then(files => files.map(file => path.join(parentDirectory, letter, file)))
  .then(files => Promise.all(files.map(parseSpellFile)));
}

const ROOT = path.resolve('source/Spellcasting');
const SPELL_FILES_ROOT = path.resolve(ROOT, 'spells_a-z');

const ALPHABET = 'abcdefghijklmnopqrstuvwxyz';

Promise.all(
  ALPHABET.split('').map(letter => parseLetterDirectory(letter, SPELL_FILES_ROOT))
).then(result => result.reduce((arr, val) => (arr.push(...val), arr), []))
.then(result => JSON.stringify(result.filter(el => el != null), null, 2))
.then(console.log, console.error);