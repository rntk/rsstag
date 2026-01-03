'use strict';
import * as d3 from 'd3';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class BiGramsGraph {
  constructor(containerSelector, tag, eventSystem) {
    this.containerSelector = containerSelector;
    this.tag = tag;
    this.ES = eventSystem;
    this.width = 900;
    this.height = 700;
    this.data = null;
    this.meta = null;
    this.svg = null;
    this.simulation = null;
    this.zoomGroup = null;
  }

  showLoading() {
    const container = d3.select(this.containerSelector);
    container.selectAll('*').remove();

    container
      .append('div')
      .style('text-align', 'center')
      .style('padding', '20px')
      .style('color', '#666')
      .style('font-size', '14px')
      .text('Loading bi-grams graph...');
  }

  fetchData() {
    this.showLoading();

    rsstag_utils
      .fetchJSON(`/api/tag-bi-grams-graph/${encodeURIComponent(this.tag)}`, {
        method: 'GET',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
      .then((response) => {
        if (response.data) {
          this.data = response.data;
          this.meta = response.meta || null;
          this.renderGraph();
        } else {
          console.error('No graph data received');
          this.renderError('No graph data available');
        }
      })
      .catch((error) => {
        console.error('Error fetching bi-grams graph data:', error);
        this.renderError('Failed to load graph data');
      });
  }

  normalizeGraphData(rawData) {
    const primaryMainId = this.meta && this.meta.main_tag ? this.meta.main_tag : this.tag;
    const nodesIn = rawData && Array.isArray(rawData.nodes) ? rawData.nodes : [];
    const linksIn =
      rawData && Array.isArray(rawData.links)
        ? rawData.links
        : rawData && Array.isArray(rawData.edges)
          ? rawData.edges
          : [];

    const idByIndex = [];
    for (let i = 0; i < nodesIn.length; i++) {
      const n = nodesIn[i];
      if (typeof n === 'string' && n) {
        idByIndex[i] = n;
      } else if (n && typeof n.id === 'string' && n.id) {
        idByIndex[i] = n.id;
      } else {
        idByIndex[i] = undefined;
      }
    }

    const resolveId = (v) => {
      if (v === null || v === undefined) return null;
      if (typeof v === 'string') return v;
      if (typeof v === 'number' && Number.isInteger(v)) {
        return idByIndex[v] || null;
      }
      if (typeof v === 'object') {
        if (typeof v.id === 'string' && v.id) return v.id;
        if (typeof v.tag === 'string' && v.tag) return v.tag;
        if (typeof v.name === 'string' && v.name) return v.name;
      }
      return null;
    };

    // Build a map of node data including frequency and bigram_frequency
    const nodeDataById = new Map();
    for (const n of nodesIn) {
      if (!n || typeof n.id !== 'string' || !n.id) continue;
      const freq = Number(n.frequency ?? n.freq ?? n.count ?? 1);
      const bigramFreq = Number(n.bigram_frequency ?? n.bigramFrequency ?? freq);
      nodeDataById.set(n.id, {
        frequency: Number.isFinite(freq) ? Math.max(1, freq) : 1,
        bigram_frequency: Number.isFinite(bigramFreq) ? Math.max(1, bigramFreq) : 1,
        type: n.type || 'related',
      });
    }

    const nodeById = new Map();

    // Ensure main node exists with proper frequency
    const mainNodeData = nodeDataById.get(primaryMainId);
    const mainFreq = mainNodeData
      ? mainNodeData.frequency
      : Number(this.meta && this.meta.main_tag_frequency ? this.meta.main_tag_frequency : 1);

    nodeById.set(primaryMainId, {
      id: primaryMainId,
      frequency: Number.isFinite(mainFreq) ? Math.max(1, mainFreq) : 1,
      type: 'main',
    });

    const buildStarLinks = (mainId) => {
      const weightByOther = new Map();
      for (const l of linksIn) {
        if (!l) continue;
        const source = resolveId(l.source ?? l.from ?? l.src);
        const target = resolveId(l.target ?? l.to ?? l.dst);
        if (typeof source !== 'string' || typeof target !== 'string') continue;

        const w = Number(
          l.weight ?? l.posts_count ?? l.count ?? l.value ?? l.freq ?? l.frequency ?? 0
        );
        if (!Number.isFinite(w) || w <= 0) continue;

        let otherId = null;
        if (source === mainId && target !== mainId) {
          otherId = target;
        } else if (target === mainId && source !== mainId) {
          otherId = source;
        }

        if (!otherId) continue;

        weightByOther.set(otherId, (weightByOther.get(otherId) || 0) + w);

        if (!nodeById.has(otherId)) {
          // Get frequency from node data, fallback to link weight
          const otherNodeData = nodeDataById.get(otherId);
          const otherFreq = otherNodeData ? otherNodeData.frequency : w; // Use link weight as frequency fallback

          nodeById.set(otherId, {
            id: otherId,
            frequency: Number.isFinite(Number(otherFreq)) ? Math.max(1, Number(otherFreq)) : 1,
            bigram_frequency: w, // Store the bi-gram co-occurrence frequency
            type: 'related',
          });
        }
      }
      return weightByOther;
    };

    // Build star links: main -> other (2nd part / other token)
    let mainId = primaryMainId;
    let weightByOther = buildStarLinks(mainId);

    // Fallback if meta main tag mismatches link endpoints
    if (
      weightByOther.size === 0 &&
      typeof this.tag === 'string' &&
      this.tag &&
      this.tag !== primaryMainId
    ) {
      const retry = buildStarLinks(this.tag);
      if (retry.size > 0) {
        mainId = this.tag;
        weightByOther = retry;
      }
    }

    const nodes = Array.from(nodeById.values());
    const links = Array.from(weightByOther.entries()).map(([otherId, weight]) => ({
      source: mainId,
      target: otherId,
      weight,
    }));

    if (links.length === 0 && linksIn.length > 0) {
      console.warn('BiGramsGraph: links dropped during normalization', {
        tag: this.tag,
        metaMainTag: this.meta && this.meta.main_tag ? this.meta.main_tag : null,
        usedMainId: mainId,
        nodesIn: nodesIn.length,
        linksIn: linksIn.length,
      });
    }

    // Log frequency data for debugging
    console.log(
      'BiGramsGraph: Node frequencies',
      nodes.map((n) => ({ id: n.id, freq: n.frequency }))
    );

    return { nodes, links, mainId };
  }

  renderNoBigramsView() {
    const container = d3.select(this.containerSelector);
    container.selectAll('*').remove();

    const mainId = this.meta && this.meta.main_tag ? this.meta.main_tag : this.tag;
    const mainTag =
      this.data && Array.isArray(this.data.nodes)
        ? this.data.nodes.find((n) => n && n.id === mainId) || this.data.nodes[0]
        : null;
    const meta = this.meta || {};

    let message = `<strong>${mainId}</strong> has no bi-gram connections.<br/>
                  This tag appears in ${mainTag && mainTag.frequency ? mainTag.frequency : 'N/A'} posts but doesn't co-occur with other tags.`;

    if (meta.main_tag_frequency) {
      message = `<strong>${meta.main_tag}</strong> (${meta.main_tag_frequency} posts) has no bi-gram connections.<br/>
                      No related tags found in the dataset.`;
    }

    container
      .append('div')
      .style('text-align', 'center')
      .style('padding', '30px')
      .style('color', '#666')
      .style('font-size', '16px')
      .style('background-color', '#f8f9fa')
      .style('border', '1px solid #e9ecef')
      .style('border-radius', '8px')
      .style('max-width', '600px')
      .style('margin', '0 auto')
      .html(message);
  }

  renderError(message) {
    const container = d3.select(this.containerSelector);
    container.selectAll('*').remove();

    container
      .append('div')
      .style('color', '#d32f2f')
      .style('padding', '10px')
      .style('background-color', '#ffebee')
      .style('border', '1px solid #ef9a9a')
      .style('border-radius', '4px')
      .style('margin', '10px 0')
      .text(message);
  }

  renderGraph() {
    if (!this.data || !this.data.nodes) {
      console.error('Invalid graph data:', this.data);
      this.renderError('Invalid graph data');
      return;
    }

    // Normalize to required structure: main tag as root, nodes are second/other tags, star links only
    const normalized = this.normalizeGraphData(this.data);
    this.data = { nodes: normalized.nodes, links: normalized.links };
    const mainId = normalized.mainId;

    // Validate and clean the data
    try {
      // Ensure nodes is an array and filter out invalid entries
      if (!Array.isArray(this.data.nodes)) {
        console.error('Nodes is not an array:', this.data.nodes);
        this.renderError('Invalid nodes data');
        return;
      }

      // Filter out any invalid nodes
      this.data.nodes = this.data.nodes.filter(
        (node) => node && node.id && typeof node.id === 'string'
      );

      // Handle case where there are no links (no bi-grams)
      if (!this.data.links) {
        this.data.links = [];
      } else if (!Array.isArray(this.data.links)) {
        console.error('Links is not an array:', this.data.links);
        this.data.links = [];
      }

      // Filter out any invalid links
      this.data.links = this.data.links.filter(
        (link) =>
          link &&
          link.source &&
          link.target &&
          Number.isFinite(Number(link.weight)) &&
          Number(link.weight) > 0
      );

      // Handle case where there are no bi-grams
      if (this.meta && this.meta.has_bigrams === false) {
        this.renderNoBigramsView();
        return;
      }

      // Handle case where there's only the main node
      if (this.data.nodes.length === 1 && this.data.links.length === 0) {
        this.renderNoBigramsView();
        return;
      }

      // Ensure we have at least one valid node
      if (this.data.nodes.length === 0) {
        this.renderError('No valid nodes found in graph data');
        return;
      }
    } catch (error) {
      console.error('Error validating graph data:', error);
      this.renderError('Error processing graph data');
      return;
    }

    // Clear previous graph
    d3.select(this.containerSelector).selectAll('*').remove();

    // Create SVG container with dark background
    this.svg = d3
      .select(this.containerSelector)
      .append('svg')
      .attr('width', this.width)
      .attr('height', this.height)
      .attr('viewBox', [-this.width / 2, -this.height / 2, this.width, this.height])
      .style('background-color', '#0a1628')
      .style('border-radius', '8px');

    // Create a group for zoomable content
    this.zoomGroup = this.svg.append('g').attr('class', 'zoom-group');

    // Calculate frequency extent for dynamic node sizing
    const frequencies = this.data.nodes.map((d) => d.frequency || 1);
    const freqExtent = d3.extent(frequencies);
    const minFreq = Math.max(1, freqExtent[0] || 1);
    const maxFreq = Math.max(1, freqExtent[1] || 1);

    // Create a scale for node radius based on frequency
    // Using sqrt scale for better visual perception (area scales with value)
    this.nodeRadiusScale = d3.scaleSqrt().domain([minFreq, maxFreq]).range([8, 60]); // Min radius 8, max radius 60

    // Log the scale for debugging
    console.log('BiGramsGraph: Frequency range', { minFreq, maxFreq });

    // Create forces with improved parameters for better connectivity and node distribution
    try {
      this.simulation = d3
        .forceSimulation(this.data.nodes)
        .force(
          'link',
          d3
            .forceLink(this.data.links)
            .id((d) => d.id)
            .distance((d) => {
              // Significantly increased distance for better node separation
              const sourceSize = this.nodeRadiusScale(
                d.source && d.source.frequency ? d.source.frequency : minFreq
              );
              const targetSize = this.nodeRadiusScale(
                d.target && d.target.frequency ? d.target.frequency : minFreq
              );
              // Much longer links to create more space between nodes
              return Math.max(300, sourceSize + targetSize + 300);
            })
            .strength(0.2) // Further reduced strength for more flexibility
        )
        .force(
          'charge',
          d3
            .forceManyBody()
            .strength((d) => {
              // Much stronger repulsion to push nodes far apart
              const size = this.nodeRadiusScale(d && d.frequency ? d.frequency : minFreq);
              return -Math.max(2500, size * 80); // Increased repulsion
            })
            .distanceMin(100)
            .distanceMax(2000)
        )
        .force('center', d3.forceCenter(0, 0).strength(0.02)) // Further reduced to allow more spreading
        .force(
          'collide',
          d3
            .forceCollide()
            .radius((d) => {
              // Calculate collision radius with more padding
              const nodeSize = this.nodeRadiusScale(d && d.frequency ? d.frequency : minFreq);
              return nodeSize + 100; // Increased padding for better separation
            })
            .strength(1)
            .iterations(6)
        ) // More iterations for better collision resolution
        .alphaDecay(0.005) // Even slower decay for better settling
        .velocityDecay(0.2);
    } catch (error) {
      console.error('Error creating force simulation:', error);
      this.renderError('Failed to create graph simulation');
      return;
    }

    // Fix the main tag at the center (root node)
    const rootNode = this.data.nodes.find((n) => n && n.id === mainId);
    if (rootNode) {
      rootNode.fx = 0;
      rootNode.fy = 0;
      rootNode.x = 0;
      rootNode.y = 0;
    }

    // Create gradient definitions for curved flow links
    const defs = this.svg.append('defs');

    const weightExtent = d3.extent(this.data.links, (d) => Number(d && d.weight) || 0);
    const minW = Math.max(1, weightExtent && weightExtent[0] ? weightExtent[0] : 1);
    const maxW = Math.max(1, weightExtent && weightExtent[1] ? weightExtent[1] : 1);
    const linkWidthScale = d3.scaleSqrt().domain([minW, maxW]).range([2, 24]);

    // Add links with Sankey-style curved paths and gradients
    const link = this.zoomGroup
      .append('g')
      .attr('class', 'links')
      .selectAll('path')
      .data(this.data.links)
      .join('path')
      .attr('fill', 'none')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', (d) => linkWidthScale(Number(d && d.weight) || 1))
      .attr('stroke-linecap', 'round')
      .each(function (d, i) {
        // Create gradient for each link
        const gradientId = `link-gradient-${i}`;
        const gradient = defs
          .append('linearGradient')
          .attr('id', gradientId)
          .attr('gradientUnits', 'userSpaceOnUse');

        // Determine colors based on direction (relative to main tag)
        const sourceId = d.source && typeof d.source === 'object' ? d.source.id : d.source;
        const isFromMain = sourceId === mainId;
        const startColor = isFromMain ? '#c94663' : '#4a90b5';
        const endColor = isFromMain ? '#b83550' : '#3a7095';

        gradient.append('stop').attr('offset', '0%').attr('stop-color', startColor);

        gradient.append('stop').attr('offset', '100%').attr('stop-color', endColor);

        d3.select(this).attr('stroke', `url(#${gradientId})`);
      })
      .on('mouseover', function (event, d) {
        if (d && d.source && d.target && d.weight) {
          const baseWidth = linkWidthScale(Number(d.weight) || 1);
          d3.select(this)
            .attr('stroke-opacity', 0.9)
            .attr('stroke-width', baseWidth * 1.3);

          const sourceName = d.source.id || d.source;
          const targetName = d.target.id || d.target;
          tooltip.style('visibility', 'visible')
            .html(`<strong>Bi-gram:</strong> ${sourceName} ↔ ${targetName}<br/>
                               <strong>Frequency:</strong> ${d.weight}`);
        }
      })
      .on('mousemove', function (event) {
        tooltip.style('top', event.pageY - 10 + 'px').style('left', event.pageX + 10 + 'px');
      })
      .on('mouseout', function (event, d) {
        if (d && d.source && d.target && d.weight) {
          const baseWidth = linkWidthScale(Number(d.weight) || 1);
          d3.select(this).attr('stroke-opacity', 0.6).attr('stroke-width', baseWidth);
        }
        tooltip.style('visibility', 'hidden');
      });

    // Add nodes with sizes based on tag frequency using the scale
    const nodeRadiusScale = this.nodeRadiusScale; // Capture for use in callbacks
    const node = this.zoomGroup
      .append('g')
      .attr('class', 'nodes')
      .selectAll('circle')
      .data(this.data.nodes)
      .join('circle')
      .attr('r', (d) => {
        // Use the pre-computed scale for consistent sizing
        return nodeRadiusScale(d && d.frequency ? d.frequency : 1);
      })
      .attr('fill', (d) => (d && d.id === mainId ? '#4a90b5' : '#c94663'))
      .attr('stroke', (d) => (d && d.id === mainId ? '#e0e6ed' : '#1a2f4a'))
      .attr('stroke-width', (d) => (d && d.id === mainId ? 4 : 2))
      .attr('opacity', 0.9) // Slight transparency to see overlapping
      .call(this.drag(this.simulation))
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        if (d && d.id) {
          this.handleNodeClick(d.id);
        }
      });

    // Add labels with improved formatting - tag on first line, frequency on second line
    const labelGroup = this.zoomGroup
      .append('g')
      .attr('class', 'label-groups')
      .selectAll('g')
      .data(this.data.nodes)
      .join('g')
      .attr('class', 'label-group')
      .attr('pointer-events', 'none');

    // Add tag text (first line)
    labelGroup
      .append('text')
      .attr('class', 'tag-label')
      .text((d) => (d && d.id ? d.id : ''))
      .attr('font-size', (d) => {
        // Scale font size based on node size
        const nodeSize = nodeRadiusScale(d && d.frequency ? d.frequency : 1);
        return Math.max(12, Math.min(18, nodeSize / 3.5)) + 'px';
      })
      .attr('dx', (d) => (d && d.id === mainId ? -15 : 20))
      .attr('dy', -10) // Position above center
      .attr('text-anchor', (d) => (d && d.id === mainId ? 'end' : 'start'))
      .attr('font-weight', (d) => (d && d.id === mainId ? 'bold' : 'normal'))
      .attr('fill', '#e0e6ed')
      .attr('opacity', 0.95)
      .attr('text-shadow', '1px 1px 2px rgba(0,0,0,0.7)');

    // Add frequency text (second line)
    labelGroup
      .append('text')
      .attr('class', 'freq-label')
      .text((d) => (d && d.frequency ? d.frequency.toString() : ''))
      .attr('font-size', (d) => {
        // Slightly smaller font for frequency
        const nodeSize = nodeRadiusScale(d && d.frequency ? d.frequency : 1);
        return Math.max(10, Math.min(14, nodeSize / 4)) + 'px';
      })
      .attr('dx', (d) => (d && d.id === mainId ? -15 : 20))
      .attr('dy', 10) // Position below center
      .attr('text-anchor', (d) => (d && d.id === mainId ? 'end' : 'start'))
      .attr('font-weight', 'normal')
      .attr('fill', '#a0b8d8')
      .attr('opacity', 0.85)
      .attr('text-shadow', '1px 1px 2px rgba(0,0,0,0.7)');

    // Add tooltip with dark theme
    const tooltip = d3
      .select(this.containerSelector)
      .append('div')
      .style('position', 'absolute')
      .style('visibility', 'hidden')
      .style('background-color', 'rgba(20, 30, 48, 0.95)')
      .style('border', '1px solid #4a5f7f')
      .style('padding', '12px')
      .style('border-radius', '6px')
      .style('pointer-events', 'none')
      .style('font-size', '13px')
      .style('color', '#e0e6ed')
      .style('box-shadow', '0 4px 12px rgba(0,0,0,0.4)')
      .style('max-width', '300px')
      .style('z-index', '1000');

    // Mouse events with enhanced tooltip showing frequency
    node
      .on('mouseover', function (event, d) {
        if (d && d.id) {
          const nodeType = d.id === mainId ? 'Main Tag' : 'Related Tag';
          const frequency = d.frequency || 'N/A';
          const bigramFreq = d.bigram_frequency || null;

          // Highlight node
          d3.select(this).attr('stroke', '#ffa500').attr('stroke-width', 4);

          let tooltipContent = `<strong>${d.id}</strong><br/>
                           <strong>Type:</strong> ${nodeType}<br/>
                           <strong>Tag Frequency:</strong> ${frequency}`;

          if (bigramFreq && nodeType !== 'Main Tag') {
            tooltipContent += `<br/><strong>Bi-gram Frequency:</strong> ${bigramFreq}`;
          }

          tooltip.style('visibility', 'visible').html(tooltipContent);
        }
      })
      .on('mousemove', function (event) {
        tooltip.style('top', event.pageY - 10 + 'px').style('left', event.pageX + 10 + 'px');
      })
      .on('mouseout', function (event, d) {
        if (d && d.id) {
          // Restore original style
          d3.select(this)
            .attr('stroke', '#1a2f4a')
            .attr('stroke-width', d.id === mainId ? 3 : 2);
        }
        tooltip.style('visibility', 'hidden');
      });

    // Update positions on each tick with custom collision detection and curved paths
    this.simulation.on('tick', () => {
      link.attr('d', (d) => {
        // Create smooth curved path (Sankey-style)
        const sourceX = d.source.x;
        const sourceY = d.source.y;
        const targetX = d.target.x;
        const targetY = d.target.y;

        const dx = targetX - sourceX;
        const dy = targetY - sourceY;
        const dr = Math.sqrt(dx * dx + dy * dy);

        // Control point for smoother curves
        const midX = (sourceX + targetX) / 2;
        const midY = (sourceY + targetY) / 2;

        // Add perpendicular offset for curve
        const offset = dr * 0.2;
        const angle = Math.atan2(dy, dx) + Math.PI / 2;
        const controlX = midX + Math.cos(angle) * offset;
        const controlY = midY + Math.sin(angle) * offset;

        return `M${sourceX},${sourceY} Q${controlX},${controlY} ${targetX},${targetY}`;
      });

      // Update gradient positions
      link.each(function (d, i) {
        const gradientId = `link-gradient-${i}`;
        const gradient = defs.select(`#${gradientId}`);
        if (!gradient.empty()) {
          gradient
            .attr('x1', d.source.x)
            .attr('y1', d.source.y)
            .attr('x2', d.target.x)
            .attr('y2', d.target.y);
        }
      });

      node.attr('cx', (d) => d.x).attr('cy', (d) => d.y);

      // Update label group positions
      labelGroup.attr('transform', (d) => `translate(${d.x},${d.y})`);

      // Custom collision detection and resolution
      this.resolveNodeCollisions();
    });

    // Stabilize simulation after it ends
    this.simulation.on('end', () => {
      console.log('Simulation ended');
    });

    // Add initial positioning to spread nodes in a circular pattern
    this.initializeNodePositions();

    // Improved zoom functionality
    this.svg
      .call(
        d3
          .zoom()
          .scaleExtent([0.2, 8])
          .on('zoom', (event) => {
            this.zoomGroup.attr('transform', event.transform);
          })
      )
      .on('dblclick.zoom', null); // Disable double-click zoom

    // Add reset button for better user control with dark theme
    const resetButton = d3
      .select(this.containerSelector)
      .append('button')
      .style('position', 'absolute')
      .style('top', '10px')
      .style('right', '10px')
      .style('padding', '8px 12px')
      .style('background-color', 'rgba(30, 45, 65, 0.9)')
      .style('color', '#e0e6ed')
      .style('border', '1px solid #4a5f7f')
      .style('border-radius', '4px')
      .style('cursor', 'pointer')
      .style('z-index', '1000')
      .style('font-size', '12px')
      .text('Reset View')
      .on('click', () => {
        this.simulation.alpha(0.5).restart();
        this.simulation.force('center', d3.forceCenter(0, 0).strength(1.5));
        this.svg
          .transition()
          .duration(750)
          .call(this.svg.call(d3.zoom().transform, d3.zoomIdentity));
      });
  }

  resolveNodeCollisions() {
    const nodes = this.data.nodes;
    const collisionPadding = 20; // Larger padding for better edge visibility

    // Create a spatial index for faster collision detection
    const gridSize = 100;
    const grid = {};

    // Clear and populate grid
    for (const node of nodes) {
      if (node.x === undefined || node.y === undefined) continue;

      const gridX = Math.floor(node.x / gridSize);
      const gridY = Math.floor(node.y / gridSize);
      const gridKey = `${gridX},${gridY}`;

      if (!grid[gridKey]) {
        grid[gridKey] = [];
      }
      grid[gridKey].push(node);
    }

    // Check for collisions and resolve them
    for (const node of nodes) {
      if (node.x === undefined || node.y === undefined) continue;
      if (node.fx !== undefined && node.fy !== undefined) continue; // Skip fixed nodes (being dragged)

      const nodeRadius = this.getNodeRadius(node);
      const searchRadius = nodeRadius * 2 + collisionPadding;

      // Check neighboring grid cells
      const minGridX = Math.floor((node.x - searchRadius) / gridSize);
      const maxGridX = Math.floor((node.x + searchRadius) / gridSize);
      const minGridY = Math.floor((node.y - searchRadius) / gridSize);
      const maxGridY = Math.floor((node.y + searchRadius) / gridSize);

      for (let gridX = minGridX; gridX <= maxGridX; gridX++) {
        for (let gridY = minGridY; gridY <= maxGridY; gridY++) {
          const gridKey = `${gridX},${gridY}`;
          const neighbors = grid[gridKey];

          if (neighbors) {
            for (const otherNode of neighbors) {
              if (otherNode === node) continue;
              if (otherNode.x === undefined || otherNode.y === undefined) continue;

              const otherRadius = this.getNodeRadius(otherNode);
              const minDistance = nodeRadius + otherRadius + collisionPadding;

              const dx = otherNode.x - node.x;
              const dy = otherNode.y - node.y;
              const distance = Math.sqrt(dx * dx + dy * dy);

              if (distance < minDistance && distance > 0) {
                // Nodes are overlapping, push them apart
                const overlap = minDistance - distance;
                const pushFactor = overlap * 0.5;

                // Push nodes away from each other
                const angle = Math.atan2(dy, dx);

                // Only move the current node if it's not fixed
                if (node.fx === undefined && node.fy === undefined) {
                  node.x -= Math.cos(angle) * pushFactor;
                  node.y -= Math.sin(angle) * pushFactor;
                }

                // Also push the other node if it's not fixed
                if (otherNode.fx === undefined && otherNode.fy === undefined) {
                  otherNode.x += Math.cos(angle) * pushFactor;
                  otherNode.y += Math.sin(angle) * pushFactor;
                }
              }
            }
          }
        }
      }
    }
  }

  getNodeRadius(node) {
    // Use the pre-computed scale if available, otherwise fall back to basic calculation
    if (this.nodeRadiusScale && node && node.frequency) {
      return this.nodeRadiusScale(node.frequency);
    }

    // Fallback calculation
    if (!node || !node.frequency) return 12;

    const baseSize = 12;
    const scaleFactor = 8;
    const minSize = 8;
    const maxSize = 60;

    const calculatedSize = baseSize + Math.log1p(node.frequency) * scaleFactor;
    return Math.max(minSize, Math.min(maxSize, calculatedSize));
  }

  initializeNodePositions() {
    const mainId = this.meta && this.meta.main_tag ? this.meta.main_tag : this.tag;
    const mainNode = this.data.nodes.find((d) => d && d.id === mainId);
    const otherNodes = this.data.nodes.filter((d) => d && d.id !== mainId);

    if (mainNode) {
      // Position main node at center but don't fix it
      mainNode.x = 0;
      mainNode.y = 0;
      mainNode.fx = 0;
      mainNode.fy = 0;
    }

    // Position other nodes in a wide circular pattern for sparse initial layout
    // Larger radius ensures edges are long enough to show their width clearly
    const baseRadius = 350;
    const radiusVariation = 100; // Add radius variation for visual interest
    const angleStep = (2 * Math.PI) / Math.max(1, otherNodes.length);

    otherNodes.forEach((node, index) => {
      const angle = index * angleStep + (Math.random() - 0.5) * 0.3; // Slight angle jitter
      const nodeRadius = baseRadius + (Math.random() - 0.5) * radiusVariation;

      node.x = Math.cos(angle) * nodeRadius;
      node.y = Math.sin(angle) * nodeRadius;
    });
  }

  drag(simulation) {
    function dragstarted(event, d) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event, d) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event, d) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }

    return d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended);
  }

  handleNodeClick(tag) {
    // Check if this is the main tag or a related tag
    const isMainTag = tag === this.tag || tag === (this.meta && this.meta.main_tag);

    // For main tag, open entity page
    // For related tags, open bi-gram page with the main tag and this tag
    if (isMainTag) {
      // Open entity page for the main tag
      window.open(`/entity/${encodeURIComponent(tag)}`, '_blank');
    } else {
      // Open bi-gram page for the combination
      const mainTag = this.meta && this.meta.main_tag ? this.meta.main_tag : this.tag;
      const biGram = `${mainTag} ${tag}`;
      window.open(`/bi-gram/${encodeURIComponent(biGram)}`, '_blank');
    }
  }

  start() {
    this.fetchData();
  }
}
