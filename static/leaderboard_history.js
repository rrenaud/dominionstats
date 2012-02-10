LeaderboardHistory = {};

LeaderboardHistory.process_raw_history_data = function (raw_history_data) {
    var entries = [],
        index,
        row,
        entry;

    for (index in raw_history_data) {
        row = raw_history_data[index];
        entry = {
            date: row[0],
            timestamp: Date.parse(row[0]),
            skill_mean: row[1],
            skill_error: row[2],
            rank: row[3],
            eligible_games_played: row[4]
        };
        entries.push(entry);
    }

    return entries;
};

LeaderboardHistory.plot_graph = function (entries, label, dom_id, callback) {
    var index,
        entry,
        points = [],
        data,
        options;

    for (index in entries) {
        entry = entries[index];
        points.push([entry.timestamp, callback(entry)]);
    }

    data = [{
        label: label,
        data: points,
        lines: {
            show: true
        }
    }];
    options = {
        legend: {
            position: 'nw'
        },
        xaxis: {
            mode: 'time',
            timeformat: '%b %d, %y'
        }
    };

    $.plot($('#' + dom_id), data, options);
};

