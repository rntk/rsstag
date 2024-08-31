'use strict';
import Sunburst from 'sunburst-chart';

export default class TagSunburst {
    constructor(data) {
        this.data = data;
        this.base_color = "#d7d7af";
        this.color_range = 20; //initial_root["children"].length / 2;  // How much each RGB value can vary;
        this.chart = Sunburst();
    }

    render(selector) {
        this.chart
            .data(this.data)
            .color(d => generateSimilarColor(this.base_color, this.color_range))
            .minSliceAngle(0)
            .onClick((d, event) => {
                if (d) {
                    let new_tag = encodeURIComponent(this.data["name"] + ' ' + d.name);
                    if (event.ctrlKey) {
                        // open new tab/window
                        window.open('/entity/' + new_tag, '_blank');
                        //window.location.href = '/entity/' + encodeURIComponent(initial_root["name"]);
                    } else {
                        window.location.href = '/sunburst/' + new_tag;
                    }
                } else {
                    let tags = this.data["name"].split(' ');
                    if (tags.length > 1) {
                        tags.pop();
                        window.location.href = '/sunburst/' + encodeURIComponent(tags.join(' '));
                    } else {
                        window.location.href = '/';
                    }
                }

            })
        (document.querySelector(selector));
    }
}

function generateSimilarColor(baseColor, range) {
    // Helper function to ensure a value is within 0-255
    const clamp = (value) => Math.min(255, Math.max(0, value));

    // Convert base color to RGB
    const baseRGB = hexToRGB(baseColor);

    // Generate new RGB values within the specified range
    const newRGB = baseRGB.map(value => {
        const min = Math.max(0, value - range);
        const max = Math.min(255, value + range);
        return clamp(Math.floor(Math.random() * (max - min + 1) + min));
    });
  // Convert back to hex
  return rgbToHex(newRGB);
}

// Helper function to convert hex to RGB
function hexToRGB(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return [r, g, b];
}

// Helper function to convert RGB to hex
function rgbToHex(rgb) {
    return '#' + rgb.map(x => {
    const hex = x.toString(16);
    return hex.length === 1 ? '0' + hex : hex;
    }).join('');
}