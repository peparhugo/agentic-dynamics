const express = require('express');
const routes = require('./routes/api');

const app = express();
const PORT = process.env.PORT || 3000;

app.set('trust proxy', 1);
app.use(express.json());

app.use('/', routes);

app.listen(PORT, () => {
  console.log(`URL shortener running on http://localhost:${PORT}`);
});
