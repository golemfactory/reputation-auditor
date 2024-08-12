import { ResultState, defaultLogger, WorkContext, Worker, ProviderInfo } from "@golem-sdk/golem-js";

import { ReputationSystem, ReputationData, ReputationWeights } from "@golem-sdk/golem-js/experimental";

type RunConfig = {
  name: string;
  count: number;
  parallel: number;
  reputation?: ReputationSystem;
};

type TestResult = {
  provider: ProviderInfo;
  testTime: number;
  consoleTime: number;
};

type TestRunResult = {
  success: number;
  failure: number;
  time: number;
  results: TestResult[];
  providerIdSet: Set<string>;
  walletAddressSet: Set<string>;
  // runTimes: number[];
  // runMin: number;
  // runMax: number;
};
const activityExecuteTimeout = 60 * 1000;
async function runTests(config: any): Promise<TestRunResult> {
  const start = performance.now();
  console.log(`Starting tests ${config.name}...`);
  const providerIdSet = new Set<string>();
  const walletAddressSet = new Set<string>();
  const executor = await TaskExecutor.create({
    payment: { network: "polygon" },
    package: "golem/alpine:latest",
    proposalFilter: config.reputation
      ? config.reputation.proposalFilter({
          min: 0.8,
        })
      : undefined,
    maxTaskRetries: 0,
    maxParallelTasks: config.parallel,
    agreementSelector: config.reputation?.agreementSelector({}),
    activityExecuteTimeout,
  });

  const promises: Promise<void>[] = [];
  const results: TestResult[] = [];
  for (let i = 0; i < config.count; i++) {
    const worker = async (ctx: WorkContext) => {
      const pi = ctx.activity.getProviderInfo();
      providerIdSet.add(pi.id);
      walletAddressSet.add(pi.walletAddress);
      const tStart = performance.now();
      // '+%s%3N' would give result in ms, but alpine's `date` does not support it.
      const result = await ctx.run("date '+%s' && sleep 10 && date '+%s'", {
        timeout: 30 * 1000,
      });
      const tEnd = performance.now();

      if (result.result === ResultState.Ok) {
        const testTime = tEnd - tStart;
        const [cStart, cEnd] = (result.stdout as string).split("\n").map(Number);

        const consoleTime = (cEnd - cStart) * 1000;

        console.log(`Test #${i} on ${pi.id} (${pi.name}) took ${(testTime / 1000).toFixed(2)}`);
        results.push({
          provider: ctx.activity.getProviderInfo(),
          testTime,
          consoleTime,
        });
      } else {
        throw new Error(`Task #$\{i} ${config.name} failed: ` + result.stderr);
      }
    };

    promises.push(executor.run(worker));
  }

  const pResults = await Promise.allSettled(promises);

  await executor.shutdown();

  let failed = 0;
  pResults.forEach((p, i) => {
    if (p.status === "rejected") {
      console.log(`Task #${i} failed: ${p.reason}`);
      failed++;
    }
  });

  return {
    failure: failed,
    success: config.count - failed,
    time: performance.now() - start,
    results,
    providerIdSet,
    walletAddressSet,
  };
}

(async function main() {
  // console.log("WARNING: This test always run on polygon, so real costs will occur.");
  // console.log("If you do not wish to continue, press Ctrl+C to abort.");
  // console.log("The test will start in 5 seconds...");
  // await sleep(5, false);

  const reputation1 = await ReputationSystem.create({
    logger: defaultLogger("app"),
    paymentNetwork: "polygon",
  });

  reputation1.setAgreementWeights({
    successRate: 0.3,
    cpuSingleThreadScore: 0.7,
  });

  // Tests specifications.
  const count = 100;
  const maxParallelTasks = 40;

  const configs: RunConfig[] = [];
  //
  // configs.push(
  //   {
  //     name: "no-rep",
  //     count,
  //     maxParallelTasks,
  //   });

  configs.push({
    name: "run",
    count,
    reputation: reputation1,
    // filterThreshold: 0.8,
    parallel: maxParallelTasks,
  });
  // configs.push(
  //   {
  //     name: "rep-0.8as",
  //     count,
  //     reputation: reputation1,
  //     filterThreshold: 0.8,
  //     agreementSelector: true,
  //     maxParallelTasks,
  //   });

  // {
  //   name: "rep-0.95",
  //   count,
  //   reputation,
  //   filterThreshold: 0.95,
  //   maxParallelTasks,
  // },

  // Run all tests.
  const status: TestRunResult[] = [];
  for (const config of configs) {
    const result = await runTests(config);
    console.log(
      "Run completed",
      // JSON.stringify(
      //   {
      //     config: {
      //       ...config,
      //       reputation: !!config.reputation, // do not output the huge object.
      //     },
      //     result
      //   },
      //   null,
      //   4,
      // ),
    );
    status.push(result);
  }

  // Display the results.
  console.log("Final results:");
  status.forEach((s, i) => {
    const config = configs[i];
    console.log(
      `\t${config.name}: ${s.success}/${config.count} - ${(s.success / config.count) * 100}% in ${(s.time / 1000).toFixed(1)}s`,
    );
    console.log(`\t\tDistinct providers: ${s.providerIdSet.size}`);
    console.log(`\t\tDistinct wallets: ${s.walletAddressSet.size}`);
    console.log("\t\tMax parallel tasks:", config.parallel);
    // console.log("\t\tAgreement selector:", s.config.agreementSelector ? "yes" : "no");
    // const runAverage = s.result.runTimes.length
    //   ? (s.result.runTimes.reduce((a, c) => a + c, 0) / s.result.runTimes.length).toFixed(1)
    //   : "N/A";

    // console.log(
    //   `\t\tBench time (min, avg, max): ${s.result.runMin.toFixed(1)}, ${runAverage}, ${s.result.runMax.toFixed(1)}`,
    // );
    console.log("\t\ttimes:");
    s.results.forEach((r, i) => {
      const deviation = ((r.testTime - r.consoleTime) / r.testTime) * 100;
      console.log(
        `\t\t\t#${i}, ${r.provider.id}: ${(r.testTime / 1000).toFixed(2)}s, ${(r.consoleTime / 1000).toFixed(2)}s - overhead ${deviation.toFixed(2)}%`,
      );
    });
  });
})();
