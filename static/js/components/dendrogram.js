'use strict';
import * as d3 from 'd3';

export default class TagTree {
    constructor(data) {
        this.data = data;
    }

    render(selector, width = 1152, height = 1152) {
        let link_fn = (d, n) => {
            let lst = n.ancestors().reverse().map(d => d.data.name);
            let link = document.location.origin + "/tree/";
            let url_tag = lst[0];
            if (lst.length > 2) {
                url_tag += " " + lst[2];
            } 

            return link + encodeURIComponent(url_tag);
        };
        let chart = Tree(this.data, {
            label: d => d.name,
            title: (d, n) => `${n.ancestors().reverse().map(d => d.data.name).join(" ")}`, // hover text
            link: link_fn,
            width: width,
            height: height,
            margin: 100
          })
        let pg = document.querySelector(selector);
        if (pg) {
            pg.innerHTML = '';
            pg.appendChild(chart);
        }
    }
}

export class BidirectionalTagTree {
    constructor(data) {
        this.data = data;
    }

    render(selector, width = 1152, height = 600) {
        let link_fn = (d, n) => {
            let lst = n.ancestors().reverse().map(d => d.data.name);
            let link = document.location.origin + "/tree/";
            let url_tag = lst[0];
            if (lst.length > 2) {
                url_tag += " " + lst[2];
            } 

            return link + encodeURIComponent(url_tag);
        };
        let chart = BidirectionalHorizontalTree(this.data, {
            label: d => d.name,
            title: (d, n) => `${n.ancestors().reverse().map(d => d.data.name).join(" ")}`, // hover text
            link: link_fn,
            width: width,
            height: height,
            margin: 100
          })
        let pg = document.querySelector(selector);
        if (pg) {
            pg.innerHTML = '';
            pg.appendChild(chart);
        }
    }
}

function BidirectionalHorizontalTree(data, {
    children,
    tree = d3.tree,
    sort,
    label,
    title,
    link,
    linkTarget = "_blank",
    width = 640,
    height = 400,
    r = 3,
    fill = "#999",
    stroke = "#555",
    strokeWidth = 1.5,
    strokeOpacity = 0.4,
    halo = "#d7d7af",
    haloWidth = 3,
    curve = d3.curveBumpX,
} = {}) {
    const root = d3.hierarchy(data, children);
    if (sort != null) root.sort(sort);

    // Split root into left and right branches
    // data structure now has "before" and "after" arrays
    const leftRoot = d3.hierarchy({name: "root", children: data.before || []});
    const rightRoot = d3.hierarchy({name: "root", children: data.after || []});

    if (sort != null) {
        leftRoot.sort(sort);
        rightRoot.sort(sort);
    }

    const dx = 40; // Vertical spacing (increased from 25)
    const dy = 200; // Horizontal spacing (increased from 150)

    const treeLayout = tree().nodeSize([dx, dy]);

    treeLayout(leftRoot);
    treeLayout(rightRoot);

    // Root position
    root.x = 0;
    root.y = 0;

    const svg = d3.create("svg")
        .attr("viewBox", [-width / 2, -height / 2, width, height])
        .attr("width", width)
        .attr("height", height)
        .attr("style", "max-width: 100%; height: auto; font-family: sans-serif; font-size: 14px; background: #fff;");

    const g = svg.append("g");

    // Add zoom
    svg.call(d3.zoom()
        .extent([[0, 0], [width, height]])
        .scaleExtent([0.1, 8])
        .on("zoom", (event) => {
            g.attr("transform", event.transform);
        }));

    // Add CSS transitions for smooth highlighting
    svg.append("style").text(`
        .link {
            transition: stroke-opacity 0.3s;
        }
        .node {
            transition: fill-opacity 0.3s;
        }
    `);

    // Helper function to find connected nodes and paths
    function findConnected(d) {
        const nodes = new Set();
        const links = new Set();
        d.ancestors().forEach(node => {
            if (node.data.name !== "root") {
                nodes.add(node);
                if (node.parent && node.parent.data.name !== "root") {
                    links.add(node.parent);
                }
            }
        });
        return { nodes, links };
    }

    // Mouse event handlers for highlighting
    function handleMouseOver(event, d) {
        const { nodes, links } = findConnected(d);
        g.selectAll(".link")
            .filter(link => !links.has(link.source))
            .attr("stroke-opacity", 0.1);
        g.selectAll(".node")
            .filter(node => !nodes.has(node))
            .attr("fill-opacity", 0.1);
    }

    function handleMouseOut() {
        g.selectAll(".link")
            .attr("stroke-opacity", strokeOpacity);
        g.selectAll(".node")
            .attr("fill-opacity", 1);
    }

    const links = [];
    const nodes = [root];

    if (leftRoot.children) {
        leftRoot.children.forEach(child => {
            child.parent = root;
            child.descendants().forEach(d => {
                d.y = -d.y - dy; // Mirror horizontal position and offset
                nodes.push(d);
            });
            
            links.push({source: root, target: child});
            child.links().forEach(l => {
                links.push(l);
            });
        });
    }

    if (rightRoot.children) {
        rightRoot.children.forEach(child => {
            child.parent = root;
            child.descendants().forEach(d => {
                d.y = d.y + dy; // Offset
                nodes.push(d);
            });
            
            links.push({source: root, target: child});
            child.links().forEach(l => {
                links.push(l);
            });
        });
    }

    // Filter out "Before" and "After" nodes from display if they are just placeholders?
    // Actually they might be useful, but let's see. 
    // The requirement is "common topic in center and before and after should be the next and previous topics"
    
    g.append("g")
        .attr("fill", "none")
        .attr("stroke", stroke)
        .attr("stroke-opacity", strokeOpacity)
        .attr("stroke-width", strokeWidth)
      .selectAll("path")
      .data(links)
      .join("path")
        .attr("d", d3.link(curve)
            .x(d => d.y)
            .y(d => d.x))
        .attr("class", "link");

    const node = g.append("g")
      .selectAll("a")
      .data(nodes)
      .join("a")
        .attr("xlink:href", link == null ? null : d => link(d.data, d))
        .attr("target", link == null ? null : linkTarget)
        .attr("transform", d => `translate(${d.y},${d.x})`)
        .attr("class", "node")
        .on("mouseover", handleMouseOver)
        .on("mouseout", handleMouseOut);

    node.append("circle")
        .attr("fill", d => d.children ? stroke : fill)
        .attr("r", r);

    if (title != null) node.append("title")
        .text(d => title(d.data, d));

    if (label) node.append("text")
        .attr("dy", "0.32em")
        .attr("x", d => d.y < 0 ? -6 : 6)
        .attr("text-anchor", d => d.y < 0 ? "end" : "start")
        .attr("paint-order", "stroke")
        .attr("stroke", halo)
        .attr("stroke-width", haloWidth)
        .text((d) => label(d.data, d));

    return svg.node();
}

// Copyright 2021-2023 Observable, Inc.
// Released under the ISC license.
// https://observablehq.com/@d3/tree
function Tree(data, { // data is either tabular (array of objects) or hierarchy (nested objects)
    path, // as an alternative to id and parentId, returns an array identifier, imputing internal nodes
    id = Array.isArray(data) ? d => d.id : null, // if tabular data, given a d in data, returns a unique identifier (string)
    parentId = Array.isArray(data) ? d => d.parentId : null, // if tabular data, given a node d, returns its parent’s identifier
    children, // if hierarchical data, given a d in data, returns its children
    tree = d3.tree, // layout algorithm (typically d3.tree or d3.cluster)
    sort, // how to sort nodes prior to layout (e.g., (a, b) => d3.descending(a.height, b.height))
    label, // given a node d, returns the display name
    title, // given a node d, returns its hover text
    link, // given a node d, its link (if any)
    linkTarget = "_blank", // the target attribute for links (if any)
    width = 640, // outer width, in pixels
    height, // outer height, in pixels
    r = 3, // radius of nodes
    padding = 1, // horizontal padding for first and last column
    fill = "#999", // fill for nodes
    fillOpacity, // fill opacity for nodes
    stroke = "#555", // stroke for links
    strokeWidth = 1.5, // stroke width for links
    strokeOpacity = 0.4, // stroke opacity for links
    strokeLinejoin, // stroke line join for links
    strokeLinecap, // stroke line cap for links
    halo = "#d7d7af", // color of label halo 
    haloWidth = 3, // padding around the labels
    curve = d3.curveBumpX, // curve for the link
  } = {}) {
  
    // If id and parentId options are specified, or the path option, use d3.stratify
    // to convert tabular data to a hierarchy; otherwise we assume that the data is
    // specified as an object {children} with nested objects (a.k.a. the “flare.json”
    // format), and use d3.hierarchy.
    const root = path != null ? d3.stratify().path(path)(data)
        : id != null || parentId != null ? d3.stratify().id(id).parentId(parentId)(data)
        : d3.hierarchy(data, children);
  
    // Sort the nodes.
    if (sort != null) root.sort(sort);
  
    // Compute labels and titles.
    const descendants = root.descendants();
    const L = label == null ? null : descendants.map(d => label(d.data, d));
  
    // Compute the layout.
    const dx = 25;
    const dy = 200;
    tree().nodeSize([dx, dy])(root);
  
    // Center the tree.
    let x0 = Infinity;
    let x1 = -x0;
    root.each(d => {
      if (d.x > x1) x1 = d.x;
      if (d.x < x0) x0 = d.x;
    });
  
    // Compute the default height.
    if (height === undefined) height = x1 - x0 + dx * 2;
  
    // Use the required curve
    if (typeof curve !== "function") throw new Error(`Unsupported curve`);
  
    const svg = d3.create("svg")
        .attr("viewBox", [-dy * padding / 2, x0 - dx, width, height])
        .attr("width", width)
        .attr("height", height)
        .attr("style", "max-width: 100%; height: auto; height: intrinsic;")
        .attr("font-family", "sans-serif")
        .attr("font-size", 14);

    const g = svg.append("g");

    // Add zoom
    svg.call(d3.zoom()
        .extent([[0, 0], [width, height]])
        .scaleExtent([0.1, 8])
        .on("zoom", (event) => {
            g.attr("transform", event.transform);
        }));

    // Add CSS transitions for smooth highlighting
    svg.append("style").text(`
        .link {
            transition: stroke-opacity 0.3s;
        }
        .node {
            transition: fill-opacity 0.3s;
        }
    `);

    // Helper function to find connected nodes and paths
    function findConnected(d) {
        const nodes = new Set();
        const links = new Set();
        d.ancestors().forEach(node => {
            nodes.add(node);
            if (node.parent) {
                links.add(node.parent);
            }
        });
        return { nodes, links };
    }

    // Mouse event handlers for highlighting
    function handleMouseOver(event, d) {
        const { nodes, links } = findConnected(d);
        g.selectAll(".link")
            .filter(link => !links.has(link.source))
            .attr("stroke-opacity", 0.1);
        g.selectAll(".node")
            .filter(node => !nodes.has(node))
            .attr("fill-opacity", 0.1);
    }

    function handleMouseOut() {
        g.selectAll(".link")
            .attr("stroke-opacity", strokeOpacity);
        g.selectAll(".node")
            .attr("fill-opacity", 1);
    }
  
    g.append("g")
        .attr("fill", "none")
        .attr("stroke", stroke)
        .attr("stroke-opacity", strokeOpacity)
        .attr("stroke-linecap", strokeLinecap)
        .attr("stroke-linejoin", strokeLinejoin)
        .attr("stroke-width", strokeWidth)
      .selectAll("path")
        .data(root.links())
        .join("path")
          .attr("d", d3.link(curve)
              .x(d => d.y)
              .y(d => d.x))
          .attr("class", "link");
  
    const node = g.append("g")
      .selectAll("a")
      .data(root.descendants())
      .join("a")
        .attr("xlink:href", link == null ? null : d => link(d.data, d))
        .attr("target", link == null ? null : linkTarget)
        .attr("transform", d => `translate(${d.y},${d.x})`)
        .attr("class", "node")
        .on("mouseover", handleMouseOver)
        .on("mouseout", handleMouseOut);
  
    node.append("circle")
        .attr("fill", d => d.children ? stroke : fill)
        .attr("r", r);
  
    if (title != null) node.append("title")
        .text(d => title(d.data, d));
  
    if (L) node.append("text")
        .attr("dy", "0.32em")
        .attr("x", d => d.children ? -6 : 6)
        .attr("text-anchor", d => d.children ? "end" : "start")
        .attr("paint-order", "stroke")
        .attr("stroke", halo)
        .attr("stroke-width", haloWidth)
        .text((d, i) => L[i]);
  
    return svg.node();
}

// Copyright 2022-2023 Observable, Inc.
// Released under the ISC license.
// https://observablehq.com/@d3/radial-tree
function RadialTree(data, { // data is either tabular (array of objects) or hierarchy (nested objects)
    path, // as an alternative to id and parentId, returns an array identifier, imputing internal nodes
    id = Array.isArray(data) ? d => d.id : null, // if tabular data, given a d in data, returns a unique identifier (string)
    parentId = Array.isArray(data) ? d => d.parentId : null, // if tabular data, given a node d, returns its parent’s identifier
    children, // if hierarchical data, given a d in data, returns its children
    tree = d3.tree, // layout algorithm (typically d3.tree or d3.cluster)
    separation = tree === d3.tree ? (a, b) => (a.parent == b.parent ? 1 : 2) / a.depth : (a, b) => a.parent == b.parent ? 1 : 2,
    sort, // how to sort nodes prior to layout (e.g., (a, b) => d3.descending(a.height, b.height))
    label, // given a node d, returns the display name
    title, // given a node d, returns its hover text
    link, // given a node d, its link (if any)
    linkTarget = "_blank", // the target attribute for links (if any)
    width = 640, // outer width, in pixels
    height = 400, // outer height, in pixels
    margin = 60, // shorthand for margins
    marginTop = margin, // top margin, in pixels
    marginRight = margin, // right margin, in pixels
    marginBottom = margin, // bottom margin, in pixels
    marginLeft = margin, // left margin, in pixels
    radius = Math.min(width - marginLeft - marginRight, height - marginTop - marginBottom) / 2, // outer radius
    r = 3, // radius of nodes
    padding = 1, // horizontal padding for first and last column
    fill = "#999", // fill for nodes
    fillOpacity, // fill opacity for nodes
    stroke = "#555", // stroke for links
    strokeWidth = 1.5, // stroke width for links
    strokeOpacity = 0.4, // stroke opacity for links
    strokeLinejoin, // stroke line join for links
    strokeLinecap, // stroke line cap for links
    halo = "#d7d7af", // color of label halo
    haloWidth = 3, // padding around the labels
  } = {}) {

    // If id and parentId options are specified, or the path option, use d3.stratify
    // to convert tabular data to a hierarchy; otherwise we assume that the data is
    // specified as an object {children} with nested objects (a.k.a. the “flare.json”
    // format), and use d3.hierarchy.
    const root = path != null ? d3.stratify().path(path)(data)
        : id != null || parentId != null ? d3.stratify().id(id).parentId(parentId)(data)
        : d3.hierarchy(data, children);

    // Sort the nodes.
    if (sort != null) root.sort(sort);

    // Compute labels and titles.
    const descendants = root.descendants();
    const L = label == null ? null : descendants.map(d => label(d.data, d));

    // Compute the layout.
    tree().size([2 * Math.PI, radius]).separation(separation)(root);

    const svg = d3.create("svg")
        .attr("viewBox", [-marginLeft - radius, -marginTop - radius, width, height])
        .attr("width", width)
        .attr("height", height)
        .attr("style", "max-width: 100%; height: auto; height: intrinsic;")
        .attr("font-family", "sans-serif")
        .attr("font-size", 14);

    svg.append("g")
        .attr("fill", "none")
        .attr("stroke", stroke)
        .attr("stroke-opacity", strokeOpacity)
        .attr("stroke-linecap", strokeLinecap)
        .attr("stroke-linejoin", strokeLinejoin)
        .attr("stroke-width", strokeWidth)
      .selectAll("path")
      .data(root.links())
      .join("path")
        .attr("d", d3.linkRadial()
            .angle(d => d.x)
            .radius(d => d.y));

    const node = svg.append("g")
      .selectAll("a")
      .data(root.descendants())
      .join("a")
        .attr("xlink:href", link == null ? null : d => link(d.data, d))
        .attr("target", link == null ? null : linkTarget)
        .attr("transform", d => `rotate(${d.x * 180 / Math.PI - 90}) translate(${d.y},0)`);

    node.append("circle")
        .attr("fill", d => d.children ? stroke : fill)
        .attr("r", r);

    if (title != null) node.append("title")
        .text(d => title(d.data, d));
    
    if (L) node.append("text")
        .attr("transform", d => `rotate(${d.x >= Math.PI ? 180 : 0})`)
        .attr("dy", "0.32em")
        .attr("x", d => d.x < Math.PI === !d.children ? 6 : -6)
        .attr("text-anchor", d => d.x < Math.PI === !d.children ? "start" : "end")
        .attr("paint-order", "stroke")
        .attr("stroke", halo)
        .attr("stroke-width", haloWidth)
        .text((d, i) => L[i]);

    return svg.node();
  }