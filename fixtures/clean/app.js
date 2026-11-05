// Clean test fixture: user input is passed as a bound parameter, not pasted into SQL.
const ms = require('ms')

async function findUser (db, id) {
  return db.query('SELECT * FROM users WHERE id = $1', [id])
}

module.exports = { findUser, timeout: ms('2s') }
