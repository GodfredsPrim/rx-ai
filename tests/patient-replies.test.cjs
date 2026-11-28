const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('static/js/app.js', 'utf8');
const snippet = source.slice(source.indexOf('const displayedPharmacistReplies'), source.indexOf('function _wsBase'));
const messages = [];
let polls = 0;
const context = vm.createContext({currentSession: {role: 'user', user_id: 7}, patientReportSyncTimer: null,
  addMsg: (...args) => messages.push(args), renderPrescriptionHistory: () => {},
  callApi: async () => { polls++; return {prescriptions: [{id: 3, pharmacist_feedback: 'Take with food'}]}; },
  setInterval: () => 1, clearInterval: () => {}});
vm.runInContext(snippet, context);
(async () => {
  await context.syncPatientReplies();
  await context.syncPatientReplies();
  context.receivePharmacistReply({case_id: 3, pharmacist_feedback: 'Take with food'});
  assert.equal(messages.length, 1, 'Polling and live delivery must deduplicate');
  assert.match(messages[0][1], /Take with food/);
  context.receivePharmacistReply({case_id: 3, pharmacist_feedback: 'Updated guidance'});
  assert.equal(messages.length, 2, 'An updated review must appear');
  context.currentSession = {role: 'guest'};
  await context.syncPatientReplies();
  assert.equal(polls, 2, 'Guests cannot poll patient replies');
  console.log('Patient reply recovery and deduplication passed');
})();
