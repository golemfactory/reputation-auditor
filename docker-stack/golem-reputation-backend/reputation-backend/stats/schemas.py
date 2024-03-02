from ninja import Schema
from typing import List, Optional

class TaskSchema(Schema):
    date: str
    successful: bool
    taskName: str
    errorMessage: str

class ResponseSchema(Schema):
    successRatio: float
    tasks: List[TaskSchema]


class BenchmarkSchema(Schema):
    timestamp: int
    singleThread: Optional[float] = None
    multiThread: Optional[float] = None

class DeviationSchema(Schema):
    singleDeviation: float
    multiDeviation: float

class BenchmarkResponse(Schema):
    benchmarks: List[BenchmarkSchema]
    singleDeviation: float
    multiDeviation: float


class SequentialBenchmarkSchema(Schema):
    timestamp: int
    writeSingleThread: Optional[float]
    readSingleThread: Optional[float]

class RandomBenchmarkSchema(Schema):
    timestamp: int
    writeMultiThread: Optional[float]
    readMultiThread: Optional[float]

class MemoryBenchmarkResponse(Schema):
    sequentialBenchmarks: List[SequentialBenchmarkSchema] = []
    randomBenchmarks: List[RandomBenchmarkSchema] = []
    sequentialWriteDeviation: Optional[float]
    sequentialReadDeviation: Optional[float]
    randomWriteDeviation: Optional[float]
    randomReadDeviation: Optional[float]


class SequentialDiskBenchmarkSchema(Schema):
    timestamp: int
    readThroughput: Optional[float]
    writeThroughput: Optional[float]

class RandomDiskBenchmarkSchema(Schema):
    timestamp: int
    readThroughput: Optional[float]
    writeThroughput: Optional[float]

class DiskBenchmarkResponse(Schema):
    sequentialDiskBenchmarks: List[SequentialDiskBenchmarkSchema] = []
    randomDiskBenchmarks: List[RandomDiskBenchmarkSchema] = []
    sequentialReadDeviation: Optional[float]
    sequentialWriteDeviation: Optional[float]
    randomReadDeviation: Optional[float]
    randomWriteDeviation: Optional[float]