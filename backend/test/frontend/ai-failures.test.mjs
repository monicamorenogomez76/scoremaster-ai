import test from 'node:test';
import assert from 'node:assert/strict';
import { aiFailure } from '../../../frontend/src/aiFailures.js';
import { sourceText } from '../../../frontend/src/explanations.js';
import { answerSource } from '../../../frontend/src/workQuestions.js';

test('each reason is told in its own words, and an unknown one as not available', () => {
  const told = ['timeout', 'rate_limit', 'invalid', 'model', 'key', 'overloaded', 'error'].map(aiFailure);
  assert.equal(new Set(told).size, told.length);
  assert.match(aiFailure('model'), /GEMINI_MODEL/);
  assert.match(aiFailure('key'), /GEMINI_API_KEY/);
  assert.equal(aiFailure('other'), aiFailure('error'));
});

test('the questions and the explanations say it', () => {
  assert.ok(answerSource({ mode: 'demo', tools: [], fallback_reason: 'model' }).startsWith(aiFailure('model')));
  assert.ok(sourceText({ mode: 'demo', fallback_reason: 'key' }).startsWith(aiFailure('key')));
});
