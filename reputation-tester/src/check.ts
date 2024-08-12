import { readFileSync } from "fs";
import { ReputationData, ReputationSystem } from "@golem-sdk/golem-js/experimental";

const data = JSON.parse(readFileSync(process.argv[2], "utf-8"));


const repData = data.results[1].reputationData as ReputationData;

console.log(repData.testedProviders.length);

const rep = new ReputationSystem();
rep.setData(repData);

const testFor = [.9, .8, .7, .6, .5, .4, .3, .2, .1, .05, .02, .01, .005, .002, .001];

rep.setProposalWeights({ cpuSingleThreadScore: 1.0 });

for (const perf of testFor) {
  console.log(`Providers with cpu score >= ${perf}: ${rep.calculateProviderPool({ min: perf }).length}`);
}

