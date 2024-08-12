import {
  AgreementCandidate,
  defaultLogger,
  GolemError,
  Proposal,
  ProposalFilter,
  ProviderInfo
} from "@golem-sdk/golem-js";
import { ReputationSystem, ReputationWeights } from "@golem-sdk/golem-js/experimental";
import { TaskExecutor, WorkContext } from "@golem-sdk/task-executor";
import { program } from "commander";
import { CandidateInfo, RunResult, TaskFailureMode, TaskResult } from "./utils/types";
import { writeFile } from "node:fs/promises";
import { renderResults } from "./utils/report-gen";

/**
 * This example runs multiple test on **polygon** in order to test the reputation quality.
 */

interface RunConfig {
  count: number;
  name: string;
  reputation?: ReputationSystem;
  agreementSelector?: boolean;
  filterThreshold?: number;
  maxParallelTasks?: number;
}



interface RunStatus {
  config: RunConfig;
  result: RunResult;
}

export const combineFilter = (...filters: ProposalFilter[]) => (proposal: Proposal) => {
  return filters.every((filter) => filter(proposal));
}

class WorkTimeoutError extends Error {
}

class ExecutorAbortedError extends Error {
}

const DEFAULT_PROPOSAL_MIN_SCORE = 0.3;

async function runTests(config: RunConfig): Promise<RunResult> {
  const name = config.name;
  const start = performance.now();
  console.log(`Starting tests ${name}...`);
  const providerIdSet = new Set<string>();
  const walletAddressSet = new Set<string>();
  let proposalsAfterFirstAgreement = 0;
  let hadFirstAgreement = false;
  let initialCandidates: CandidateInfo[]|undefined;

  // let knownProvidersSet: Set<string> = new Set();
  let seenProviders: Set<string> = new Set();
  let acceptedProviders: Set<string> = new Set();


  const options: any = {
    payment: { network: "polygon" },
    package: "golem/alpine:latest",
    maxTaskRetries: 0,
    maxParallelTasks: config.maxParallelTasks ?? 100,
  };

  if (config.reputation) {
    options.proposalFilter = combineFilter(
      // Log proposal
      (proposal: Proposal) => {
        seenProviders.add(proposal.provider.id);
        return true;
      },
      // Reputation proposal filter
      config.reputation.proposalFilter({
        acceptUnlisted: false,
        min: config.filterThreshold ?? DEFAULT_PROPOSAL_MIN_SCORE,
      }),
      // Proposal counter
      (proposal: Proposal) => {
        if (hadFirstAgreement) {
          proposalsAfterFirstAgreement++;
        }
        acceptedProviders.add(proposal.id);
        return true;
      }
    );
  } else {
    options.proposalFilter = (proposal: Proposal) => {
      seenProviders.add(proposal.provider.id);
      acceptedProviders.add(proposal.provider.id);
      return true;
    };
  }

  if (config.reputation && config.agreementSelector) {
    const selector = config.reputation.agreementSelector({
      topPoolSize: 2,
      agreementBonus: 0,
    });
    options.agreementSelector = (candidates: AgreementCandidate[]) => {
      if (!initialCandidates) {
        initialCandidates = candidates.map(c => ({
          provider: c.proposal.provider,
          score: config.reputation!.calculateScore(
            config.reputation!.getProviderScores(c.proposal.provider.id)!,
            config.reputation!.getAgreementWeights()
          ),
        }));
      }
      return selector(candidates);
    }
  }

  let executorAborted = false;

  const executor = await TaskExecutor.create({
    ...options,
    ...{
      taskTimeout: 180 * 1000,
      activityPreparingTimeout: 100 * 1000,
    }
  });
  // executor.events.on("criticalError", (err: Error) => {
  //   executorAborted = true;
  // });

  if (config.reputation) {
    console.log("Proposals weights:", config.reputation.getProposalWeights());
    console.log("Agreement weights:", config.reputation.getAgreementWeights());
  }

  const promises: Promise<void>[] = [];
  let workTimeouts = 0;
  let activityTimeouts = 0
  let abortedTasks = 0;
  const tasks: TaskResult[] = [];
  for (let i = 0; i < config.count; i++) {
    const task: TaskResult = {
      timeToStart: -1,
      activityId: '',
      failureMode: TaskFailureMode.OK,
      runTime: -1,
      index: i,
      provider: {
        id: '',
        name: '',
        walletAddress: '',
      },
      success: false,
      totalTime: -1,
      proposalScore: -1,
      agreementScore: -1,
    }
    tasks.push(task);
    const scheduleTime = performance.now();

    console.log(`Running task #${i} ${name}`);
    const worker = async (ctx: WorkContext) => {
      const pi = ctx.activity.getProviderInfo();
      task.provider = pi;
      task.activityId = ctx.activity.id;
      const on = `${pi.id} (${pi.name})`;
      providerIdSet.add(pi.id);
      walletAddressSet.add(pi.walletAddress);


      console.log(`Started task #${i} ${name} on ${on}`);

      if (config.reputation) {
        const scores = config.reputation.getProviderScores(pi.id)!;
        task.proposalScore = config.reputation
          .calculateScore(scores, config.reputation.getProposalWeights());
        task.agreementScore = config.agreementSelector
          ? config.reputation.calculateScore(scores!, config.reputation.getAgreementWeights())
          : -1;
      }

      try {
        const bStart = performance.now();
        task.timeToStart = (bStart - scheduleTime) / 1000;
        const result = await ctx.run("dd if=/dev/urandom count=1000 bs=1M of=/dev/stdout | gzip > /dev/null", {
          timeout: 60 * 1000,
        });
        const bEnd = performance.now();
        const runtime = (bEnd - bStart) / 1000;
        task.runTime = runtime;
        task.totalTime = task.runTime + task.timeToStart;
        task.success = true;



        if (result.result !== "Ok") {
          console.log(`Task #${i} ${name} failed on ${on}`);
          throw new Error("Computation failed: " + result.stdout);
        } else {
          if (config.reputation) {
            const aScore = task.agreementScore > -1 ? task.agreementScore.toFixed(2) : 'n/a';
            const pScore = task.proposalScore.toFixed(2);
            const score = `pScore: ${pScore}, aScore: ${aScore}`;
            console.log(`Task #${i} ${name} succeeded in ${runtime.toFixed(1)} on ${on}, ${score}`);
          } else {
            console.log(`Task #${i} ${name} succeeded in ${runtime.toFixed(1)} on ${on}, no score`);
          }
        }
      } catch (e) {
        if ("previous" in (e as any)) {
          const f = e as GolemError;
          if (f.constructor.name === "GolemWorkError" && f.previous?.constructor.name === "GolemTimeoutError") {
            workTimeouts++;
            throw new WorkTimeoutError("Work timeout");
          }
        }

        throw e;
      }
    };

    promises.push(executor.run(worker).catch(e => {
      if (executorAborted) {
        throw new ExecutorAbortedError("Executor aborted");
      } else {
        throw e;
      }
    }));
  }

  const result = await Promise.allSettled(promises);
  const end = performance.now();
  console.log("All tasks resolved.");


  const runTimes = tasks.map(t => t.runTime);
  const runMin = Math.min(...runTimes.filter(x => x >= 0)) ?? -1;
  const runMax = Math.max(...runTimes.filter(x => x >= 0)) ?? -1;

  let success = 0;
  let failure = 0;
  result.forEach((res, index) => {
    if (res.status === "fulfilled") {
      success++;
    } else {
      if (res.reason.constructor.name === "GolemWorkError" && res.reason.previous?.constructor.name === "GolemTimeoutError") {
        activityTimeouts++;
        tasks[index].failureMode = TaskFailureMode.ActivityTimeout;
        console.log(`Task #${index} error: Activity timeout:`, res.reason);
      } else if (res.reason instanceof WorkTimeoutError) {
        tasks[index].failureMode = TaskFailureMode.WorkTimeout;
        workTimeouts++;
        console.log(`Task #${index} error: Work timeout: `, res.reason);
      } else if (res.reason instanceof ExecutorAbortedError) {
        tasks[index].failureMode = TaskFailureMode.Aborted;
        abortedTasks++;
        console.log(`Task #${index} error: Executor aborted: `, res.reason);
      } else {
        tasks[index].failureMode = TaskFailureMode.Other;
        console.log(`Task #${index} error:`, res.reason);
      }
      failure++;
    }
  });

  console.log("All tasks done, shutting down task executor...");
  const eStart = performance.now();
  await executor.shutdown();
  const eEnd = performance.now();
  console.log(`Task executor terminated in ${((eEnd - eStart) / 1000).toFixed(2)}s.`);

  // return [success, failure, end - start];
  return {
    name: config.name,
    success,
    failure,
    time: end - start,
    providerIds: Array.from(providerIdSet.values()),
    walletAddresses: Array.from(walletAddressSet.values()),
    runMax,
    runMin,
    runTimes,
    providersMatchingFilter: config.reputation?.calculateProviderPool({min: config.filterThreshold ?? DEFAULT_PROPOSAL_MIN_SCORE}).length ?? 0,
    activityTimeouts,
    taskExecutorFailure: executorAborted,
    abortedTasks,
    workTimeouts,
    proposalsAfterFirstAgreement,
    tasks,
    initialCandidates,
    seenProviders: Array.from(seenProviders.values()),
    acceptedProviders: Array.from(acceptedProviders.values()),
    reputationData: config.reputation?.getData(),
  };
}

const agreementWeights: ReputationWeights = {
  successRate: 0,
  cpuSingleThreadScore: 1,
};


async function main(runName: string): Promise<RunResult[]> {
  // console.log("WARNING: This test always run on polygon, so real costs will occur.");
  // console.log("If you do not wish to continue, press Ctrl+C to abort.");
  // console.log("The test will start in 5 seconds...");
  // await sleep(5, false);

  const fWeights: ReputationWeights = {
    // successRate: 0.5,
    cpuSingleThreadScore: 1,
  };

  const reputation1 = await ReputationSystem.create({
    logger: defaultLogger("app"),
    paymentNetwork: "polygon",
  });
  reputation1.setProposalWeights(fWeights);
  const repData = reputation1.getData();

  const reputation2 = await ReputationSystem.create({
    logger: defaultLogger("app"),
    paymentNetwork: "polygon",
  });
  reputation2.setProposalWeights(fWeights);

  // reputation2.setProposalWeights({
  //   successRate: 0.5,
  //   cpuSingleThreadScore: 0.5,
  // });
  reputation2.setAgreementWeights(agreementWeights);

  // Tests specifications.
  const count = 100;
  const maxParallelTasks = 40;
  const configs: RunConfig[] = [];
  //
  configs.push({
    name: "no-rep",
    count,
    maxParallelTasks,
  });

  configs.push({
    name: "rep",
    count,
    reputation: reputation1,
    filterThreshold: 0.3,
    maxParallelTasks,
  });
  configs.push({
    name: "rep-full",
    count,
    reputation: reputation2,
    filterThreshold: 0.3,
    agreementSelector: true,
    maxParallelTasks,
  });

  // {
  //   name: "rep-0.95",
  //   count,
  //   reputation,
  //   filterThreshold: 0.95,
  //   maxParallelTasks,
  // },

  for (const config of configs) {
    if (!config.reputation) {
      continue
    }

    const pool = config.reputation.calculateProviderPool({
      min: config.filterThreshold ?? DEFAULT_PROPOSAL_MIN_SCORE
    });
    console.log(`Provider pool for ${config.name}: ${pool.length}`);
    if (pool.length === 0) {
      console.log('Cannot run test without providers, aborting.');
      process.exit(1);
    } else if (pool.length < 10) {
      console.log('Provider pool is small, test may not be representative.');
    }
  }

  // Run all tests.
  const status: RunStatus[] = [];
  for (const config of configs) {
    await runTests(config).then((result) => {
      const st = {
        config,
        result,
      };
      console.log(
        "Run completed:",
        JSON.stringify(
          {
            config: {
              ...config,
              reputation: !!config.reputation, // do not output the huge object.
            },
            result: {
              ...result,
            },
          },
          null,
          4,
        ),
      );
      status.push(st);
    });
  }

  // Display the results.
  console.log("Final results:");
  status.forEach((s) => {
    console.log(
      `\t${s.config.name}: ${s.result.success}/${s.config.count} - ${(s.result.success / s.config.count) * 100}% in ${(s.result.time / 1000).toFixed(1)}s`,
    );
    const other = s.result.failure - s.result.abortedTasks - s.result.workTimeouts - s.result.activityTimeouts;
    console.log(`\t\tFailures: aborted=${s.result.abortedTasks}, bench timeouts=${s.result.workTimeouts}, activity timeouts=${s.result.activityTimeouts}, other=${other}`);
    console.log(`\t\tTask executor failure: ${s.result.taskExecutorFailure}`);
    console.log(`\t\tProviders matching filter: ${s.result.providersMatchingFilter}`);
    console.log(`\t\tDistinct providers: ${s.result.providerIds.length}`);
    console.log(`\t\tDistinct wallets: ${s.result.walletAddresses.length}`);
    console.log("\t\tMax parallel tasks:", s.config.maxParallelTasks);
    console.log("\t\tAgreement selector:", s.config.agreementSelector ? "yes" : "no");
    const runAverage = s.result.runTimes.length
      ? (s.result.runTimes.reduce((a, c) => a + c, 0) / s.result.runTimes.length).toFixed(1)
      : "N/A";

    if (runAverage === "N/A") {
      console.log("\t\tBench time (min, avg, max): N/A, N/A, N/A");
    } else {
      console.log(
        `\t\tBench time (min, avg, max): ${s.result.runMin.toFixed(1)}, ${runAverage}, ${s.result.runMax.toFixed(1)}`,
      );
    }
  });
  
  return status.map(s => s.result);
}

program
  .option('-d, --dir <directory>', 'Directory to save the results', './')
  .argument('<name>', 'Test run name')
  .action(async (name, options) => {
      const results = await main(name);
      await writeFile(`${options.dir}/${name}.json`, JSON.stringify({
        results
      }, null, 4));
      await writeFile(`${options.dir}/${name}.html`, await renderResults(results));
  })
  .parse(process.argv);
