// Deliberately vulnerable. Test fixture only.
const express = require('express')
const { Sequelize } = require('sequelize')
const app = express()
const sequelize = new Sequelize('sqlite::memory:')

app.get('/user', async (req, res) => {
  // Planted problem: user input pasted straight into SQL.
  const query = "SELECT * FROM users WHERE id = '" + req.query.id + "'"
  const [rows] = await sequelize.query(query)
  res.send(rows)
})

app.listen(3000)
