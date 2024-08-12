import { RunResult } from "./types";
import { readFile } from "node:fs/promises";
import * as path from "node:path";
import {configure, renderString} from "nunjucks";

export async function renderResults(results: RunResult[]): Promise<string> {
  const template = await readFile(path.join(__dirname, "../templates/report.html"), "utf-8");

  configure({
  })
  return renderString(template, {
    reportData: results
  });
}
