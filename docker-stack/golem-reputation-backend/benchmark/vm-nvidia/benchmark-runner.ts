import { VmNvidiaBenchmarkRunnerOptions } from "./types";
import pino, { Logger } from "pino";
import { Golem } from "./golem";
import {
  bulkSubmitTaskStatuses,
  delay,
  sendBulkTaskCostUpdates,
  sendStartTaskSignal,
  sendStopTaskSignal,
  submitBulkBenchmark
} from "../utils";
import { Benchmark, TaskCompletion } from "../types";

let totalRunCost = 0;

const providerRunCost = new Map<string, number>;

// const IMAGE_NVIDIA_SMI = 'c317251c8e48a74e73f2bf0b74937a2d7e33e0a06ed04e043ab9e2ab';
const IMAGE_BURN_TEST = '2318ef1a316f7e2710b514d4541360a40ecfe3d0e05f250384488eea4137484b';

async function setupGolem(options: VmNvidiaBenchmarkRunnerOptions, taskId: string, logger: Logger): Promise<Golem> {
  const events = new EventTarget();
  const EXPECTED_EXECUTION_TIME_SECONDS = 60 * 20
  const EXPECTED_DEPLOYMENT_TIME_SECONDS = 180; //60
  const EXPECTED_TOTAL_DURATION_SECONDS = EXPECTED_EXECUTION_TIME_SECONDS + EXPECTED_DEPLOYMENT_TIME_SECONDS

  const PRICE_GLM_HOUR = parseFloat(process.env["PRICE_GLM_HOUR"] ?? "3")
  const DURATION_HOURS = EXPECTED_TOTAL_DURATION_SECONDS / 3600

  const REQUEST_START_TIMEOUT_SEC = 240;//90

  events.addEventListener("GolemEvent", (event: any) => {
    if (event.name === "PaymentAccepted") {
      // console.log(event.detail)
      const cost = Number(event.detail.amount)
      totalRunCost += cost
      // providerRunCost.set(event.detail.provider.id, cost)
      providerRunCost.set(event.detail.providerId, cost)
    }
  })


  const golem = new Golem({
    initTimeoutSec: 180,//90,
    requestStartTimeoutSec: REQUEST_START_TIMEOUT_SEC,
    requestTimeoutSec: EXPECTED_EXECUTION_TIME_SECONDS,
    deploy: {
      // imageHash: "c317251c8e48a74e73f2bf0b74937a2d7e33e0a06ed04e043ab9e2ab",
      //imageHash: IMAGE_NVIDIA_SMI,
      imageHash: IMAGE_BURN_TEST,
      // manifest: manifest.toString("base64"),
      maxReplicas: options.maxRuns,
      resources: { minCpu: 1, minMemGib: 0.5, minStorageGib: 12 },
      downscaleIntervalSec: 90,
      readyTimeoutSec: EXPECTED_DEPLOYMENT_TIME_SECONDS,
    },
    market: {
      // budget: pricePerHour,
      priceGlmPerHour: PRICE_GLM_HOUR,
      rentHours: DURATION_HOURS,
      // withoutProviders: blacklistedProviders,
      // withoutOperators: blacklistedOperators,
      // statsData: STATS_PAGE_PROVIDER_OFFERS,
    },
    // taskId: 'some-task-id',
    computedAlready: [],
    eventTarget: events,
    taskId,
  }, logger);

  return golem;
}

export async function runTasks(options: VmNvidiaBenchmarkRunnerOptions, golem: Golem, logger: Logger, taskId: string): Promise<void> {
  const promises: Promise<void>[] = [];
  let benchmarkData: Benchmark[] = []
  const taskStatuses: TaskCompletion[] = [];
  const taskIdNum = Number(taskId);
  logger.info(`Running GPU reputation task #${taskId}`);

  for (let i = 0; i < options.maxRuns; i++) {
    logger.info(`Scheduling task ${i}`);
    promises.push(
      golem.sendTask(async (ctx) => {
        try {
          let lastResult: string = '0';
          logger.info(`Running task ${i} on ${ctx.provider?.id} (${ctx.provider?.name})`);
          const result = await ctx.run("nvidia-smi --query-gpu=name,pcie.link.gen.max,memory.total,memory.free,compute_cap --format=csv,noheader,nounits")
          // const result = await ctx.run('uname -a');
          logger.info(`Task ${i} result: ${result.stdout}`);
          const data = (result.stdout as string).split("\n")
            .map((line) => line.split(",").map((v) => v.trim()))[0];
          logger.info(`Task ${i} parsed: ${data}`);

          try {
            const burnTest = await ctx.run("cd /app && ./gpu_burn 20");
            // console.log('Success', burnTest.result);
            // console.log('STDERR', burnTest.stderr);
            // console.log('STDOUT', burnTest.stdout);

            for (const result of (burnTest.stdout as string).matchAll(/\(([0-9]+)\ Gflop\/s\)/g)) {
              lastResult = result[1];
            }
            logger.info(`Task ${i} Burn test result: ${lastResult} Gflop/s on ${data[0]} - ${ctx.provider?.id} (${ctx.provider?.name})`);
          } catch (e) {
            logger.error(e, `Task ${i} Burn test failed`);
          }


          taskStatuses.push({
            task_id: taskIdNum,
            task_name: "gpu-reputation",
            node_id: ctx.provider?.id!,
            is_successful: true,
            type: "GPU",
          });

          benchmarkData.push({
            type: "gpu",
            data: {
              node_id: ctx.provider?.id!,
              name: data[0],
              pcie: Number(data[1]),
              memory_total: Number(data[2]),
              memory_free: Number(data[3]),
              cuda_cap: Number(data[4]),
              gpu_burn_gflops: Number(lastResult),
            }
          })
        } catch (e) {
          taskStatuses.push({
            task_id: taskIdNum,
            task_name: "gpu-reputation",
            node_id: ctx.provider?.id!,
            is_successful: false,
            error_message: (e as any).toString(),
            type: "GPU",
          });
          throw e;
        }
      }).catch((e) => {
        logger.error(e, `Task ${i} failed`);

        throw e;
      })
    );
  }

  await Promise.allSettled(promises);

  await submitBulkBenchmark(benchmarkData, logger)
  await bulkSubmitTaskStatuses(taskStatuses, logger);

  logger.info({data: benchmarkData}, 'Benchmark data');
  logger.info({data: taskStatuses}, 'Benchmark task statuses');


  let bulkUpdates = []

  for (const key of providerRunCost.keys()) {
    const cost = providerRunCost.get(key)

    if (typeof cost === "number") {
      logger.info({providerId: key, cost}, `Cost for provider`)
      bulkUpdates.push({ taskId, providerId: key, cost })
    } else {
      logger.error(`Cost for provider ${key} is undefined`)
    }
  }

  if (bulkUpdates.length > 0) {
    await sendBulkTaskCostUpdates(bulkUpdates, logger).then((result) => {
      if (result === "success") {
        logger.info("Bulk task cost updates sent successfully.")
      } else {
        logger.error("Error in sending bulk task cost updates.")
      }
    })
  } else {
    logger.info("No cost updates to send.")
  }

  logger.info({totalRunCost}, `Total running cost: ${totalRunCost}`)

  logger.info(`Terminated GPU reputation task #${taskId}`);
}

export async function benchmarkRunner(options: VmNvidiaBenchmarkRunnerOptions): Promise<void> {
  const logger: Logger = pino({
    level: process.env.DEBUG ? "debug" : "info",
  });

  logger.info(options, "Benchmarking vm-nvidia");

  // Allocate new task ID in the reputation system;
  logger.info(`Allocating new GPU reputation task`);
  const taskId = await sendStartTaskSignal(logger);

  const golem = await setupGolem(options, taskId, logger);
  try {
    await golem.start();
  } catch (error) {
    logger.error(error, "Failed to start golem");
    return;
  }

  if (options.dryRun) {
    logger.info({ duration: options.dryRunDuration }, "Dry run enabled. Waiting for offers.");
    await delay(options.dryRunDuration * 1000);
  } else {
    try {
      await runTasks(options, golem, logger, taskId);
    } catch (e) {

    }
  }

  await sendStopTaskSignal(taskId, totalRunCost, logger);


  try {
    logger.info("Stopping golem");
    await golem.stop();
  } catch (error) {
    logger.error(error, "Failed to stop golem");
  }
}
