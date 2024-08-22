import 'dotenv/config';

import { Command } from "commander";
import { benchmarkRunner } from "./benchmark-runner";
import { AllowDeny } from "./types";

function myParseInt(value: string, dummyPrevious: number) {
  return parseInt(value, 10);
}

function parseAndJoinList(value: string, previous: string[]): string[] {
  return [...previous, ...value.split(',')];
}

interface VmNvidiaCliOptions {
  accept: string[];
  reject: string[];
  count: number;
  testOffers: number;
}

const program = new Command();
program
  .option('-a, --accept <providers>', 'Comma-separated list of provider IDs to accept, all others will be rejected.', parseAndJoinList, [])
  .option('-r, --reject <providers>', 'Comma-separated list of provider IDs to reject, all others will be accepted.', parseAndJoinList, [])
  .option('-c, --count <count>', 'Number of providers to run the benchmark on.', myParseInt, 200)
  .option('-t, --test-offers <duration>', 'Test only, do not accept any offers. Duration in seconds.', myParseInt, 0)


program.action(async (options: VmNvidiaCliOptions) => {
  // Validate all options firs.
  if (options.accept.length > 0 && options.reject.length > 0) {
    throw new Error('Cannot accept and reject providers at the same time. Choose either one or the other.');
  }

  // Run the benchmark.
  await benchmarkRunner({
    dryRun: options.testOffers > 0,
    dryRunDuration: options.testOffers,
    maxRuns: options.count,
    providerList: options.accept.length > 0 ? options.accept : options.reject,
    allowDeny: options.accept.length > 0 ? AllowDeny.ALLOW : AllowDeny.DENY,
  });

});

program.parse(process.argv);
