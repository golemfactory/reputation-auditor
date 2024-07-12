import { ProviderInfo } from "@golem-sdk/golem-js";
import { ReputationData } from "@golem-sdk/golem-js/experimental";

export interface TaskResult {
  index: number;
  success: boolean;
  failureMode: TaskFailureMode,
  provider: ProviderInfo;
  activityId: string;
  runTime: number;
  totalTime: number;
  /** Time between the task was scheduled and actually starting working */
  timeToStart: number;
  proposalScore: number;
  agreementScore: number;
}

export interface CandidateInfo {
  provider: ProviderInfo;
  score: number;
}

export interface RunResult {
  name: string;
  success: number;
  failure: number;
  workTimeouts: number;
  activityTimeouts: number;
  abortedTasks: number;
  taskExecutorFailure: boolean;
  time: number;
  /** Providers that were running tasks */
  providerIds: string[];
  walletAddresses: string[];
  runTimes: number[];
  runMin: number;
  runMax: number;
  providersMatchingFilter: number;
  /** How many new proposals arrived after the first agreement */
  proposalsAfterFirstAgreement: number;
  tasks: TaskResult[];
  initialCandidates?: CandidateInfo[];
  seenProviders: string[];
  acceptedProviders: string[];
  reputationData?: ReputationData;
}

export enum TaskFailureMode {
  OK = "ok",
  WorkTimeout = "work-timeout",
  ActivityTimeout = "activity-timeout",
  Aborted = "executor-aborted",
  Other = "other",
}