const fs = require('fs');
const path = require('path');
const Papa = require('papaparse');

const directoryPath = path.join(__dirname, '.'); // Replace with your directory

let globalMetrics = {}; // Object to hold aggregated metrics

fs.readdir(directoryPath, function (err, files) {
    if (err) {
        return console.log('Unable to scan directory: ' + err);
    }

    files.forEach(function (file, index) {
        let fullPath = path.join(directoryPath, file);
        let content = fs.readFileSync(fullPath, 'utf8');

        Papa.parse(content, {
            header: true,
            complete: (result) => {
                let data = result.data;

                data.forEach(row => {
                    if (row['nodeId'] === 'undefined' || !row['nodeId'] ||
                        row['ping (tcp)'] === 'undefined' || !row['ping (tcp)'] ||
                        row['ping (udp)'] === 'undefined' || !row['ping (udp)']) {
                        return; // Skip invalid or undefined rows
                    }

                    let tcpPing = convertPingToMilliseconds(row['ping (tcp)']);
                    let udpPing = convertPingToMilliseconds(row['ping (udp)']);
                    let nodeId = row['nodeId'];

                    if (!globalMetrics[nodeId]) {
                        globalMetrics[nodeId] = { totalTcpPing: 0, totalUdpPing: 0, count: 0 };
                    }

                    globalMetrics[nodeId].totalTcpPing += tcpPing;
                    globalMetrics[nodeId].totalUdpPing += udpPing;
                    globalMetrics[nodeId].count += 1;
                });

                if (index === files.length - 1) {
                    writeAggregatedDataToCSV(globalMetrics);
                }
            }
        });
    });
});

function convertPingToMilliseconds(pingValue) {
    if (pingValue.endsWith('ms')) {
        return parseFloat(pingValue.replace('ms', ''));
    } else if (pingValue.endsWith('s')) {
        return parseFloat(pingValue.replace('s', '')) * 1000;
    } else {
        return 0; // Return 0 if format is unrecognized
    }
}

function writeAggregatedDataToCSV(metrics) {
    let csvContent = "nodeId,averageTcpPing,averageUdpPing\n"; // CSV header

    for (let nodeId in metrics) {
        let nodeMetrics = metrics[nodeId];
        let avgTcpPing = nodeMetrics.totalTcpPing / nodeMetrics.count;
        let avgUdpPing = nodeMetrics.totalUdpPing / nodeMetrics.count;

        csvContent += `${nodeId},${avgTcpPing},${avgUdpPing}\n`;
    }

    fs.writeFileSync('aggregated_metrics.csv', csvContent);
    console.log('Aggregated metrics written to aggregated_metrics.csv');
}
