// Advisor conversation identity.
//
// Stored in sessionStorage (not localStorage) on purpose: an accidental page
// refresh keeps the same conversation — profile, college list, essays, timeline
// all intact — but closing the tab or coming back later starts fresh. The
// "New conversation" button rotates the id on demand.
const KEY = 'kp2c.session_id'

function rand() {
  return 'sess_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36)
}

export function getSessionId() {
  let id
  try {
    id = sessionStorage.getItem(KEY)
    if (!id) {
      id = rand()
      sessionStorage.setItem(KEY, id)
    }
  } catch (_) {
    id = rand()
  }
  return id
}

export function resetSessionId() {
  const id = rand()
  try {
    sessionStorage.setItem(KEY, id)
  } catch (_) {}
  return id
}
