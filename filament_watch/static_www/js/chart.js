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
                var shift = chg_chart.series[0].data.length > 120;

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
                $('#bed_target').html(state.bed_target);
                $('#bed_actual').html(state.bed_actual);
                $('#tool0_target').html(state.tool0_target);
                $('#tool0_actual').html(state.tool0_actual);
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
            minPadding: 0.2,
            maxPadding: 0.2,
            title: {
                text: 'mm/sec',
                margin: 80
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
