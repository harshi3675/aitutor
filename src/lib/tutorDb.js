const DB_NAME = 'ai-personalized-tutor-assets';
const DB_VERSION = 1;
const STORE = 'personas';

export const defaultTutors = [
  { id: 'default-calm', name: 'Nova Mentor', voiceMode: 'default', defaultVoice: 'calm-mentor', imageUrl: 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400"><rect width="400" height="400" fill="%230f172a"/><circle cx="200" cy="145" r="78" fill="%2338bdf8"/><path d="M70 380c20-90 240-90 260 0" fill="%238b5cf6"/><circle cx="172" cy="135" r="10"/><circle cx="228" cy="135" r="10"/><path d="M165 180q35 30 70 0" stroke="%23000" stroke-width="12" fill="none" stroke-linecap="round"/></svg>' },
  { id: 'default-coach', name: 'Echo Coach', voiceMode: 'default', defaultVoice: 'energetic-coach', imageUrl: 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400"><rect width="400" height="400" fill="%23111827"/><circle cx="200" cy="145" r="82" fill="%23f0abfc"/><path d="M65 380c26-105 244-105 270 0" fill="%2314b8a6"/><circle cx="170" cy="135" r="10"/><circle cx="230" cy="135" r="10"/><path d="M160 178q40 38 80 0" stroke="%23000" stroke-width="12" fill="none" stroke-linecap="round"/></svg>' }
];

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'id' });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx(mode, work) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE, mode);
    const store = transaction.objectStore(STORE);
    const result = work(store);
    transaction.oncomplete = () => { db.close(); resolve(result?.result ?? result); };
    transaction.onerror = () => { db.close(); reject(transaction.error); };
  });
}

export async function listTutors() {
  const records = await tx('readonly', (store) => store.getAll());
  return records.map((record) => ({ ...record, imageUrl: URL.createObjectURL(record.imageBlob) }));
}

export async function createTutor({ name, imageFile, voiceMode, voiceFile, defaultVoice }) {
  const record = { id: crypto.randomUUID(), name, imageBlob: imageFile, voiceMode, voiceBlob: voiceFile || null, defaultVoice, createdAt: new Date().toISOString() };
  await tx('readwrite', (store) => store.put(record));
  return record;
}

export async function deleteTutor(id) { await tx('readwrite', (store) => store.delete(id)); }
