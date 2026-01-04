// import * as d3 from 'd3';

export default class TopicFlow {
    constructor(data, containerSelector) {
        this.data = data;
        this.containerSelector = containerSelector;
        // Calculation logic: Root value is sum of children values
        this.data.value = this.calculateValue(this.data);

        // Sort children by value (descending) to put biggest values at top
        if (this.data.children) {
            this.data.children.sort((a, b) => b.value - a.value);
        }

        this.config = {
            width: 1200, // Intrinsic width
            height: 800, // Intrinsic height
            margin: { top: 60, right: 300, bottom: 60, left: 300 }, // Increased margins for labels
            stepHeight: 120, // Vertical space between branches
            trunkColor: '#800040', // Deep maroon/purple
            branchColorRange: ['#A02060', '#D04080', '#E060A0', '#F080C0'],
            labelColor: '#333',
            fontFamily: 'sans-serif'
        };

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
        return inputSum;
    }

    init() {
        this.render();
        // Debounced resize handler could be added here
        window.addEventListener('resize', () => this.render());
    }

    render() {
        const container = document.querySelector(this.containerSelector);
        if (!container) return;
        container.innerHTML = '';

        const { width, margin, stepHeight } = this.config;

        // Dynamic height based on number of children to ensure everything fits verticaly
        const requiredHeight = (this.data.children.length + 1) * stepHeight + margin.top + margin.bottom;
        const height = Math.max(this.config.height, requiredHeight);

        const svg = d3.select(container)
            .append('svg')
            .attr('width', '100%')
            .attr('height', '100%') // Let CSS control the container height, but SVG scales
            .attr('viewBox', `0 0 ${width} ${height}`)
            .attr('preserveAspectRatio', 'xMidYMid meet')
            .style('background', '#fff'); // Ensure visibility

        // Group structure: 
        // SVG -> MainGroup (handles margin) -> Scene (handles Zoom) -> Drawing

        // We want the zoom to affect the content, but starting nicely centered.
        // We'll create a group that holds everything.
        const scene = svg.append('g')
            .attr('class', 'scene');

        // Setup Zoom
        const zoom = d3.zoom()
            .scaleExtent([0.1, 5])
            .on('zoom', (event) => {
                scene.attr('transform', event.transform);
            });

        svg.call(zoom);

        // Store for external controls
        this.svg = svg;
        this.zoom = zoom;

        // Drawing Logic
        // We draw relative to (0,0) of the scene.
        const drawingWidth = width - margin.left - margin.right;

        // Scale for line thickness
        // Max trunk width is 30% of total width to leave room for branches
        const thicknessScale = d3.scaleLinear()
            .domain([0, this.data.value])
            .range([0, Math.min(200, drawingWidth * 0.5)]);

        // Initial Trunk State
        let currentTrunkWidth = thicknessScale(this.data.value);
        // Center the trunk in the drawing area.
        // Drawing Area starts at margin.left.
        const centerX = margin.left + drawingWidth / 2;

        let currentTrunkLeft = centerX - currentTrunkWidth / 2;
        let currentTrunkRight = centerX + currentTrunkWidth / 2;
        let currentY = margin.top;

        // Draw Root Node (Top Label)
        scene.append('text')
            .attr('x', centerX)
            .attr('y', currentY - 25)
            .attr('text-anchor', 'middle')
            .style('font-family', this.config.fontFamily)
            .style('font-size', '18px')
            .style('font-weight', 'bold')
            .style('fill', this.config.labelColor)
            .text(`${this.data.name} (${this.data.value})`);

        // Process children
        this.data.children.forEach((child, index) => {
            const childThickness = thicknessScale(child.value);
            const nextY = currentY + stepHeight;

            // Determine side
            const side = child.side || (index % 2 === 0 ? 'left' : 'right');

            let trunkNextLeft = currentTrunkLeft;
            let trunkNextRight = currentTrunkRight;

            // Branch Coordinates
            let branchTargetX, branchTargetY;

            if (side === 'left') {
                // Branch peels from Left of Trunk
                // Trunk narrows from Left
                trunkNextLeft += childThickness;

                const startX_outer = currentTrunkLeft;
                const startX_inner = currentTrunkLeft + childThickness;

                // Target: Left Margin Area
                // margin.left is e.g. 300. 
                // We want to end around x = 50 (relative to 0) to leave space.
                branchTargetX = 50;
                branchTargetY = currentY + stepHeight * 0.7;

                // Draw Branch Ribbon
                const context = d3.path();

                // Top Edge (Outer Trunk -> Target Top)
                context.moveTo(startX_outer, currentY);
                context.bezierCurveTo(
                    startX_outer, currentY + stepHeight * 0.6,
                    branchTargetX + 100, branchTargetY,
                    branchTargetX, branchTargetY
                );

                // Bottom Edge (Target Bottom -> Inner Trunk)
                const targetThickness = childThickness;

                context.lineTo(branchTargetX, branchTargetY + targetThickness);
                context.bezierCurveTo(
                    branchTargetX + 100, branchTargetY + targetThickness,
                    startX_inner, currentY + stepHeight * 0.6,
                    startX_inner, currentY
                );
                context.closePath();

                scene.append('path')
                    .attr('d', context.toString())
                    .attr('fill', this.getColor(index))
                    .attr('opacity', 0.85);

                // Label
                scene.append('text')
                    .attr('x', branchTargetX - 10)
                    .attr('y', branchTargetY + targetThickness / 2)
                    .attr('text-anchor', 'end')
                    .attr('dominant-baseline', 'middle')
                    .style('font-family', this.config.fontFamily)
                    .style('font-size', '14px')
                    .style('fill', this.config.labelColor)
                    .text(`${child.name} (${child.value})`);

            } else {
                // Branch peels from Right of Trunk
                // Trunk narrows from Right
                trunkNextRight -= childThickness;

                const startX_inner = currentTrunkRight - childThickness;
                const startX_outer = currentTrunkRight;

                // Target: Right Margin Area
                // width (1200) - 50 = 1150
                branchTargetX = width - 50;
                branchTargetY = currentY + stepHeight * 0.7;

                const context = d3.path();

                // Top Edge (Outer Trunk -> Target Top)
                context.moveTo(startX_outer, currentY);
                context.bezierCurveTo(
                    startX_outer, currentY + stepHeight * 0.6,
                    branchTargetX - 100, branchTargetY,
                    branchTargetX, branchTargetY
                );

                // Bottom Edge
                const targetThickness = childThickness;
                context.lineTo(branchTargetX, branchTargetY + targetThickness);
                context.bezierCurveTo(
                    branchTargetX - 100, branchTargetY + targetThickness,
                    startX_inner, currentY + stepHeight * 0.6,
                    startX_inner, currentY
                );
                context.closePath();

                scene.append('path')
                    .attr('d', context.toString())
                    .attr('fill', this.getColor(index))
                    .attr('opacity', 0.85);

                // Label
                scene.append('text')
                    .attr('x', branchTargetX + 10)
                    .attr('y', branchTargetY + targetThickness / 2)
                    .attr('text-anchor', 'start')
                    .attr('dominant-baseline', 'middle')
                    .style('font-family', this.config.fontFamily)
                    .style('font-size', '14px')
                    .style('fill', this.config.labelColor)
                    .text(`${child.name} (${child.value})`);
            }

            // Draw Central Trunk Connection
            // Draw Central Trunk Connection (only if not the last child)
            if (index < this.data.children.length - 1) {
                const trunkContext = d3.path();
                trunkContext.moveTo(currentTrunkLeft, currentY);
                trunkContext.lineTo(currentTrunkRight, currentY);

                // Curve sides to new width
                trunkContext.bezierCurveTo(
                    currentTrunkRight, currentY + stepHeight * 0.6,
                    trunkNextRight, currentY + stepHeight * 0.6,
                    trunkNextRight, nextY
                );

                trunkContext.lineTo(trunkNextLeft, nextY);

                trunkContext.bezierCurveTo(
                    trunkNextLeft, currentY + stepHeight * 0.6,
                    currentTrunkLeft, currentY + stepHeight * 0.6,
                    currentTrunkLeft, currentY
                );
                trunkContext.closePath();

                scene.append('path')
                    .attr('d', trunkContext.toString())
                    .attr('fill', this.config.trunkColor)
                    .attr('opacity', 1.0);
            }

            // Advance
            currentTrunkLeft = trunkNextLeft;
            currentTrunkRight = trunkNextRight;
            currentY = nextY;
        });
    }

    getColor(index) {
        const colors = this.config.branchColorRange;
        return colors[index % colors.length];
    }

    zoomIn() {
        if (this.svg && this.zoom) {
            this.svg.transition().duration(300).call(this.zoom.scaleBy, 1.2);
        }
    }

    zoomOut() {
        if (this.svg && this.zoom) {
            this.svg.transition().duration(300).call(this.zoom.scaleBy, 0.8);
        }
    }

    resetZoom() {
        if (this.svg && this.zoom) {
            this.svg.transition().duration(300).call(this.zoom.transform, d3.zoomIdentity);
        }
    }
}
