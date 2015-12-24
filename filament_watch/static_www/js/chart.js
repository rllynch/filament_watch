/*jslint browser: true, devel: true*/
/*global $,Highcharts*/

var chg_chart;

/**
 * Request data from the server, add it to the graph and set a timeout
 * to request again
 */
function requestData() {
    "use strict";
    $.ajax({
        url: 'gen_change',
        success: function (state) {
            if (state.hasOwnProperty('printing')) {
                // If the server has more history, or the first point of the
                // client history is more than 10 sec off from the server
                // history (e.g. tablet suspended then woke up with web page)
                // then reload the data
                if (chg_chart.series[0].data.length < state.gcode_history.length
                        || chg_chart.series[1].data.length < state.actual_history.length
                        || Math.abs(chg_chart.series[0].data[0].x - state.gcode_history[0][0]) > 10 * 1000
                        || Math.abs(chg_chart.series[1].data[0].x - state.actual_history[0][0]) > 10 * 1000) {
                    console.log('Reloading data from server');
                    chg_chart.series[0].setData(state.gcode_history);
                    chg_chart.series[1].setData(state.actual_history);
                }

                var shift = chg_chart.series[0].data.length >= state.history_length;

                // append point, shifting if more than 300 points
                chg_chart.series[0].addPoint(state.gcode, true, shift);
                chg_chart.series[1].addPoint(state.actual, true, shift);

                var armed_html = 'Yes';
                if (!state.valid) {
                    if (state.printing) {
                        armed_html = 'No (valid in ' + state.time_to_valid + ' sec)';
                    } else {
                        armed_html = 'No';
                    }
                }

                $('#printing').html(state.printing ? 'Yes' : 'No');
                $('#alarm').html(state.alarm ? 'Yes' : 'No');
                $('#armed').html(armed_html);
                $('#summary').html(state.summary);
                $('#filament_pos').html(state.filament_pos);
                $('#file_pos').html(state.file_pos);
                //$('#bed_target').html(state.bed_target);
                //$('#bed_actual').html(state.bed_actual);
                $('#bed').html(state.bed_actual + ' / ' + state.bed_target);
                //$('#tool0_target').html(state.tool0_target);
                //$('#tool0_actual').html(state.tool0_actual);
                $('#tool0').html(state.tool0_actual + ' / ' + state.tool0_target);
                $('#log_msgs').html(state.log_msgs);
                console.log(state);
            } else {
                $('#summary').html('Invalid state received from server');
                console.log('Invalid state: ' + state);
            }

            // call it again after one second
            setTimeout(requestData, 1000);
        },
        error: function (jqXHR, textStatus, errorThrown) {
            $('#summary').html('Error retrieving state: ' + jqXHR);
            console.log(jqXHR);
            // keep trying
            setTimeout(requestData, 1000);
        },
        cache: false
    });
}

$(document).ready(function () {
    "use strict";
    Highcharts.setOptions({
        global: {
            useUTC: false
        }
    });

    chg_chart = new Highcharts.Chart({
        chart: {
            renderTo: 'chg_chart',
            defaultSeriesType: 'spline',
            events: {
                load: requestData
            }
        },
        plotOptions: {
            spline: {
                marker: {
                    enabled: false
                }
            }
        },
        title: {
            text: 'Filament change vs. time'
        },
        xAxis: {
            type: 'datetime',
            tickPixelInterval: 150,
            maxZoom: 20 * 1000
        },
        yAxis: {
            min: 0,
            title: {
                text: 'mm/sec'
            }
        },
        series: [
            {
                name: 'GCode',
                data: []
            },
            {
                name: 'Actual',
                data: []
            }
        ]
    });
});
