// import * as d3 from 'd3';

export default class TopicFlow {
    constructor(data, containerSelector) {
        this.data = data;
        this.containerSelector = containerSelector;

        // Configurable constraints
        this.config = {
            width: 1200,
            height: 1000,
            margin: { top: 60, right: 300, bottom: 60, left: 300 },
            stepHeight: 80, // Reduced step height to pack them nicer
            trunkColor: '#800040',
            labelColor: '#333',
            fontFamily: 'sans-serif',
            curveRadius: 400, // Maximum curve influence
            minCurveRadius: 50
        };

        // Recalculate values
        this.data.value = this.calculateValue(this.data);

        // Assign sides and sort for layout
        // We need 'left' and 'right' groups
        // Heuristic: If side not present, alternate
        if (this.data.children) {
            this.data.children.forEach((child, i) => {
                if (!child.side) {
                    child.side = i % 2 === 0 ? 'left' : 'right';
                }
            });

            // Sort by value descending for the "Peeling Order" (Top to Bottom)
            // Biggest items peel first -> Must be on OUTSIDE of stack
            this.data.children.sort((a, b) => b.value - a.value);
        }

        this.init();
    }

    calculateValue(node) {
        if (!node.children || node.children.length === 0) {
            return node.value || 0;
        }
        let inputSum = 0;
        node.children.forEach(child => {
            if (child.value === undefined) {
                child.value = this.calculateValue(child);
            }
            inputSum += child.value;
        });
        return inputSum; // Only sum of children
    }

    init() {
        this.render();
        window.addEventListener('resize', () => this.render());
    }

    render() {
        const container = document.querySelector(this.containerSelector);
        if (!container) return;
        container.innerHTML = '';

        const { width, margin, stepHeight } = this.config;

        // 1. Calculate Geometry
        // Vertical space
        const childCount = this.data.children ? this.data.children.length : 0;
        const requiredHeight = (childCount * stepHeight) + margin.top + margin.bottom + 200; // Extra buffer
        const height = Math.max(this.config.height, requiredHeight);

        // Drawing Area
        const drawW = width - margin.left - margin.right;
        const centerX = margin.left + drawW / 2;

        // Scale Logic
        // Total trunk width at top
        const maxTrunkWidth = Math.min(300, drawW * 0.6); // Max 300px wide trunk
        const scale = this.data.value ? (maxTrunkWidth / this.data.value) : 0;

        // 2. Prepare Stack Layout (X Positions at the Top)
        // Order: Lefts(Largest..Smallest) -> Rights(Smallest..Largest)
        // This placement ensures Large items are on the outside.

        const lefts = this.data.children.filter(c => c.side === 'left');
        const rights = this.data.children.filter(c => c.side !== 'left');

        // Lefts are already sorted Descending (Large..Small). 
        // We place them Left->Right, so Large is Leftmost (Outside). Correct.

        // Rights are sorted Descending.
        // We need them Small..Large (Inside..Outside) for Left->Right stacking on the right side.
        const rightsStackOrder = [...rights].reverse();

        const stackOrder = [...lefts, ...rightsStackOrder];

        let currentStackX = centerX - (this.data.value * scale) / 2;

        // Assign X and Width
        stackOrder.forEach(child => {
            child._width = child.value * scale;
            child._x = currentStackX;
            currentStackX += child._width;
        });

        // 3. Setup SVG
        const svg = d3.select(container)
            .append('svg')
            .attr('width', '100%')
            .attr('height', '100%')
            .attr('viewBox', `0 0 ${width} ${height}`)
            .attr('preserveAspectRatio', 'xMidYMid meet')
            .style('background', '#fff');

        const scene = svg.append('g').attr('class', 'scene');

        // Zoom
        const zoom = d3.zoom()
            .scaleExtent([0.1, 5])
            .on('zoom', (e) => scene.attr('transform', e.transform));
        svg.call(zoom);
        this.svg = svg;
        this.zoom = zoom;

        // 4. Draw Header
        scene.append('text')
            .attr('x', centerX)
            .attr('y', margin.top - 30)
            .attr('text-anchor', 'middle')
            .style('font-family', this.config.fontFamily)
            .style('font-size', '20px')
            .style('font-weight', 'bold')
            .style('fill', this.config.labelColor)
            .text(`${this.data.name} (${this.data.value})`);

        // 5. Draw Flows
        // We iterate in the original sorted order (Descending Value) to peel from top down.
        let currentPeelY = margin.top;

        this.data.children.forEach((child, i) => {
            const peelY = currentPeelY;
            const flowW = child._width;

            // Branch Geometry
            const isLeft = child.side === 'left';
            const labelX = isLeft ? 50 : (width - 50); // Target X near margins

            // We want a nice circular arc. 
            // The horizontal distance defines the radius.
            // Dist from "Outermost Edge of Trunk for this flow" to "Label X".

            // Coords at Top (Trunk)
            const trunkLeft = child._x;
            const trunkRight = child._x + flowW;

            let path = d3.path();

            if (isLeft) {
                // Flowing Left
                // Top Edge (Left side of trunk bar) moves to Left Margin

                const startX = trunkLeft;
                const endX = labelX;
                const R = Math.abs(startX - endX); // Radius

                // Define the arc center point
                // Curve is roughly a quarter circle from Vertical to Horizontal

                const centerX = labelX; // Center of curvature X
                const centerY = peelY;  // Center of curvature Y
                // Radius for inner curve (trunkRight) is distance from labelX to trunkRight
                // radius = trunkLeft - labelX (Width of arc)

                // Left Branch Trace (Clockwise for shape closure, or any order)
                // 1. Move to Top Left (trunkLeft, 0)
                path.moveTo(trunkLeft, margin.top - 10);
                path.lineTo(trunkLeft, peelY);

                // 2. Arc Left (Inner/Top curve of the branch)
                // radius = trunkLeft - labelX.
                // Center = (labelX, peelY).
                // From Angle 0 (at trunkLeft) to Angle PI/2 (at labelX, below)
                // Wait. Canvas Arc angles: 0 is East. PI/2 is South.
                // TrunkLeft is East of Center. 
                // So Start Angle is 0. 
                // We want to go to South? (labelX, peelY + R). Yes.
                path.arc(centerX, centerY, trunkLeft - labelX, 0, Math.PI / 2);

                // Now at (labelX, peelY + radius). 
                // 3. Line to branch tip
                path.lineTo(labelX - 10, peelY + (trunkLeft - labelX));

                // 4. Line Down (width)
                // We are at Y_top = peelY + (trunkLeft - labelX).
                // We go to Y_bottom = Y_top + flowW.
                // Note: trunkRight - labelX = (trunkLeft + flowW) - labelX = (trunkLeft - labelX) + flowW.
                // So Y_bottom corresponds to radius of trunkRight!
                path.lineTo(labelX - 10, peelY + (trunkRight - labelX));

                // 5. Line Back to Arc start position (labelX)
                path.lineTo(labelX, peelY + (trunkRight - labelX));

                // 6. Arc Back Up (Outer/Bottom curve of the branch)
                // radius = trunkRight - labelX.
                // Counter-Clockwise from PI/2 to 0.
                path.arc(centerX, centerY, trunkRight - labelX, Math.PI / 2, 0, true);

                // 7. Line Up to Top
                path.lineTo(trunkRight, margin.top - 10);
                path.closePath();

                // Label
                scene.append('text')
                    .attr('x', labelX - 15)
                    .attr('y', peelY + (trunkLeft - labelX) + flowW / 2)
                    .attr('text-anchor', 'end')
                    .style('font-family', this.config.fontFamily)
                    .attr('dominant-baseline', 'middle')
                    .text(`${child.name} (${Math.round(child.value)})`);

            } else {
                // Right Branch
                // Mirror logic.
                // Turn is to the RIGHT.
                // Center (labelX, peelY).
                // trunkRight is West of Center.
                // Angle PI.
                // We want to go to South (PI/2).

                const centerX = labelX;
                const centerY = peelY;

                // 1. Move to Top Right (trunkRight, 0)
                path.moveTo(trunkRight, margin.top - 10);
                path.lineTo(trunkRight, peelY);

                // 2. Arc Right (Inner/Top curve of branch)
                // Radius = labelX - trunkRight.
                // Start Angle PI. End Angle PI/2.
                // Counter-Clockwise (PI -> PI/2). True.
                path.arc(centerX, centerY, labelX - trunkRight, Math.PI, Math.PI / 2, true);

                // 3. Tip
                path.lineTo(labelX + 10, peelY + (labelX - trunkRight));
                path.lineTo(labelX + 10, peelY + (labelX - trunkLeft)); // Width down
                path.lineTo(labelX, peelY + (labelX - trunkLeft));

                // 4. Arc Back (Outer/Bottom curve)
                // Radius = labelX - trunkLeft.
                // Clockwise (PI/2 -> PI). False.
                path.arc(centerX, centerY, labelX - trunkLeft, Math.PI / 2, Math.PI, false);

                // 5. Up
                path.lineTo(trunkLeft, margin.top - 10);
                path.closePath();

                // Label
                scene.append('text')
                    .attr('x', labelX + 15)
                    .attr('y', peelY + (labelX - trunkRight) + flowW / 2)
                    .attr('text-anchor', 'start')
                    .style('font-family', this.config.fontFamily)
                    .attr('dominant-baseline', 'middle')
                    .text(`${child.name} (${Math.round(child.value)})`);
            }

            // Draw
            scene.append('path')
                .attr('d', path.toString())
                .attr('fill', this.config.trunkColor)
                .attr('opacity', 0.85)
                .on('mouseenter', function () { d3.select(this).attr('opacity', 1); })
                .on('mouseleave', function () { d3.select(this).attr('opacity', 0.85); });

            // Increment Y
            currentPeelY += stepHeight;
        });
    }
}
