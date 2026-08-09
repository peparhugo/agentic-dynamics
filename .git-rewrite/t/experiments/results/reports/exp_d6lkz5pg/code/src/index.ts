import express from "express";
import routes from "./routes.js";

const app = express();
const PORT = parseInt(process.env.PORT || "3000", 10);

app.set("trust proxy", 1);

app.use(express.json());

app.use("/", routes);

app.listen(PORT, () => {
  console.log(`URL shortener running on http://localhost:${PORT}`);
});
