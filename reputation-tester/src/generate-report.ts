import { readFile } from "node:fs/promises";
import { renderResults } from "./utils/report-gen";
import { program } from "commander";

async function generateReport(sourceFile: string): Promise<void> {
  const input = JSON.parse(await readFile(sourceFile, "ascii"));
  console.log(await renderResults(input.results));
}


program
  .argument("<sourceFile>", "source file with results")
  .action(generateReport)
  .parse();
