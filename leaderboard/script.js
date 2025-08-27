async function fetchJSONFiles() {
    const resultsFolder = "https://fexga.github.io/basht2ranking/results/";

    try {
        const filenames = ["optuna_mnist_resource_metrics.json"];
        const rankings = [];

        for (const filename of filenames) {
            const fileUrl = `${resultsFolder}${filename}`;
            const response = await fetch(fileUrl);
            const jsonData = await response.json();

            if (jsonData.total && jsonData.total.f1_score) {
                rankings.push({
                    file: filename,
                    f1_score: jsonData.total.f1_score,
                    total_energy_kwh: jsonData.total.total_energy_kwh || (jsonData.total.total_energy_joules ? jsonData.total.total_energy_joules / 3600000 : 0),
                    total_energy_cf: jsonData.total.total_energy_cf || 0,
                    setup_energy_kwh: jsonData.steps?.setup?.total_energy_kwh || (jsonData.steps?.setup?.total_energy_joules ? jsonData.steps.setup.total_energy_joules / 3600000 : 0),
                    run_energy_kwh: jsonData.steps?.run?.total_energy_kwh || (jsonData.steps?.run?.total_energy_joules ? jsonData.steps.run.total_energy_joules / 3600000 : 0),
                    deploy_energy_kwh: jsonData.steps?.deploy?.total_energy_kwh || (jsonData.steps?.deploy?.total_energy_joules ? jsonData.steps.deploy.total_energy_joules / 3600000 : 0),
                    total_duration: jsonData.total.duration_seconds || 0
                });
            }
        }

        rankings.sort((a, b) => b.f1_score - a.f1_score);
        displayRankings(rankings);
    } catch (error) {
        console.error("Error fetching JSON files:", error);
    }
}

function displayRankings(rankings) {
    const table = document.getElementById("rankings-table");
    // Remove old rows except header
    while (table.rows.length > 1) {
        table.deleteRow(1);
    }
    rankings.forEach((ranking, index) => {
        const row = table.insertRow();
        row.insertCell(0).textContent = index + 1;
        row.insertCell(1).textContent = ranking.file;
        row.insertCell(2).textContent = ranking.f1_score.toFixed(4);
        row.insertCell(3).textContent = ranking.total_energy_kwh.toExponential(3);
        row.insertCell(4).textContent = ranking.total_energy_cf.toFixed(2);
        row.insertCell(5).textContent = ranking.setup_energy_kwh.toExponential(3);
        row.insertCell(6).textContent = ranking.run_energy_kwh.toExponential(3);
        row.insertCell(7).textContent = ranking.deploy_energy_kwh.toExponential(3);
        row.insertCell(8).textContent = ranking.total_duration.toFixed(2);
    });
}

window.onload = fetchJSONFiles;