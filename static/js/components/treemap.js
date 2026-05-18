'use strict';

export default class TagTreemap {
  constructor(data) {
    this.data = data;
    this.base_color = '#d7d7af';
    this.color_range = 20;
    this.maxChildrenPerChart = 50; // Split if more than this many children
    this.currentPage = 0;
    this.charts = [];
    this.splitData = null;
    this.initializeCharts();
  }

  initializeCharts() {
    // Check if we need to split the data
    if (this.data.children && this.data.children.length > this.maxChildrenPerChart) {
      this.splitData = this.createSplitData();
      this.charts = this.splitData.map(() => ({})); // Placeholder objects for treemap charts
    } else {
      this.charts = [{}]; // Single placeholder object
      this.splitData = [this.data];
    }
  }

  createSplitData() {
    const children = this.data.children;
    const chunks = [];

    for (let i = 0; i < children.length; i += this.maxChildrenPerChart) {
      const chunk = children.slice(i, i + this.maxChildrenPerChart);
      chunks.push({
        ...this.data,
        children: chunk,
        _pageInfo: {
          current: Math.floor(i / this.maxChildrenPerChart),
          total: Math.ceil(children.length / this.maxChildrenPerChart),
          startIndex: i,
          endIndex: Math.min(i + this.maxChildrenPerChart, children.length),
        },
      });
    }

    return chunks;
  }

  render(selector) {
    const container = document.querySelector(selector);

    if (!container) {
      console.error('Container not found for selector:', selector);
      return;
    }

    // Clear existing content
    container.innerHTML = '';

    // Create chart container
    const chartContainer = document.createElement('div');
    chartContainer.id = 'treemap-chart-container';
    container.appendChild(chartContainer);

    // Create navigation if we have multiple charts
    if (this.splitData.length > 1) {
      this.createNavigation(container);
    }

    // Render current chart
    this.renderCurrentChart(chartContainer);
  }

  createNavigation(container) {
    const nav = document.createElement('div');
    nav.className = 'treemap-navigation';
    nav.style.cssText = `
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            padding: 10px;
            background: #f5f5f5;
            border-radius: 5px;
        `;

    const info = this.splitData[this.currentPage]._pageInfo;

    // Previous button
    const prevBtn = document.createElement('button');
    prevBtn.textContent = '← Previous';
    prevBtn.disabled = this.currentPage === 0;
    prevBtn.onclick = () => this.navigateToPage(this.currentPage - 1);
    prevBtn.style.cssText = `
            padding: 5px 10px;
            border: 1px solid #ccc;
            background: ${prevBtn.disabled ? '#f0f0f0' : '#fff'};
            cursor: ${prevBtn.disabled ? 'not-allowed' : 'pointer'};
            border-radius: 3px;
        `;

    // Page info
    const pageInfo = document.createElement('span');
    pageInfo.textContent = `Page ${info.current + 1} of ${info.total} (showing ${info.startIndex + 1}-${info.endIndex} of ${this.data.children.length} tags)`;
    pageInfo.style.cssText = 'font-weight: bold; margin: 0 15px;';

    // Next button
    const nextBtn = document.createElement('button');
    nextBtn.textContent = 'Next →';
    nextBtn.disabled = this.currentPage === this.splitData.length - 1;
    nextBtn.onclick = () => this.navigateToPage(this.currentPage + 1);
    nextBtn.style.cssText = `
            padding: 5px 10px;
            border: 1px solid #ccc;
            background: ${nextBtn.disabled ? '#f0f0f0' : '#fff'};
            cursor: ${nextBtn.disabled ? 'not-allowed' : 'pointer'};
            border-radius: 3px;
        `;

    nav.appendChild(prevBtn);
    nav.appendChild(pageInfo);
    nav.appendChild(nextBtn);
    container.appendChild(nav);
  }

  navigateToPage(pageIndex) {
    if (pageIndex < 0 || pageIndex >= this.splitData.length) return;

    this.currentPage = pageIndex;
    const chartContainer = document.querySelector('#treemap-chart-container');
    if (chartContainer) {
      this.renderCurrentChart(chartContainer);
    }

    // Update navigation
    const container = chartContainer.parentElement;
    const nav = container.querySelector('.treemap-navigation');
    if (nav) {
      nav.remove();
      this.createNavigation(container);
    }
  }

  renderCurrentChart(container) {
    // Clear container
    container.innerHTML = '';

    const currentData = this.splitData[this.currentPage];

    if (!currentData || !currentData.children || currentData.children.length === 0) {
      console.error('No data to render');
      container.innerHTML = '<p>No data available</p>';
      return;
    }

    // Create treemap container
    const treemapDiv = document.createElement('div');
    treemapDiv.style.cssText = `
            width: 100%;
            max-width: 800px;
            height: 600px;
            border: 1px solid #ccc;
            position: relative;
            background: #f9f9f9;
            margin: 0 auto;
        `;

    // Get actual container dimensions
    const containerWidth = Math.min(800, container.offsetWidth || 800);
    const containerHeight = 600;

    // Calculate total value
    const totalValue = currentData.children.reduce(
      (sum, child) => sum + (child.value || child.size || 1),
      0
    );

    // Create rectangles using a simple treemap algorithm
    const rectangles = this.calculateRectangles(
      currentData.children,
      containerWidth,
      containerHeight,
      totalValue
    );

    rectangles.forEach((rect, index) => {
      const child = currentData.children[index];

      const tile = document.createElement('div');
      tile.style.cssText = `
                position: absolute;
                left: ${rect.x}px;
                top: ${rect.y}px;
                width: ${rect.width}px;
                height: ${rect.height}px;
                background: ${generateSimilarColor(this.base_color, this.color_range)};
                border: 1px solid #fff;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: ${Math.min(rect.width / 6, rect.height / 2, 18)}px;
                color: #000;
                cursor: pointer;
                overflow: hidden;
                box-sizing: border-box;
                transition: all 0.2s ease;
            `;
      tile.textContent = child.name || `Item ${index}`;

      // Add hover effects
      tile.onmouseenter = () => {
        tile.style.transform = 'scale(1.02)';
        tile.style.zIndex = '10';
        tile.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
      };

      tile.onmouseleave = () => {
        tile.style.transform = 'scale(1)';
        tile.style.zIndex = '1';
        tile.style.boxShadow = 'none';
      };

      tile.onclick = (event) => {
        event.stopPropagation(); // Prevent triggering parent onclick
        if (child) {
          let new_tag = encodeURIComponent((currentData['name'] || '') + ' ' + (child.name || ''));
          if (event.ctrlKey || event.metaKey) {
            window.open('/entity/' + new_tag, '_blank');
          } else {
            window.location.href = '/treemap/' + new_tag;
          }
        }
      };

      treemapDiv.appendChild(tile);
    });

    // Add back navigation to treemap container (similar to sunburst center click)
    treemapDiv.onclick = (event) => {
      // Only trigger if clicking the background, not a tile
      if (event.target === treemapDiv) {
        let tags = (currentData['name'] || '').split(' ');
        if (tags.length > 1) {
          tags.pop();
          window.location.href = '/treemap/' + encodeURIComponent(tags.join(' '));
        } else {
          window.location.href = '/';
        }
      }
    };

    container.appendChild(treemapDiv);
  }

  // Simple squarified treemap algorithm
  calculateRectangles(children, width, height, totalValue) {
    const rectangles = [];

    // Sort children by value in descending order for better layout
    const sortedChildren = [...children].sort(
      (a, b) => (b.value || b.size || 1) - (a.value || a.size || 1)
    );

    // Initialize layout variables
    let currentX = 0;
    let currentY = 0;
    let remainingWidth = width;
    let remainingHeight = height;

    // Process children in chunks to create rows
    let startIndex = 0;

    while (startIndex < sortedChildren.length) {
      // Find the best row of items that fit well
      const rowInfo = this.findBestRow(
        sortedChildren,
        startIndex,
        remainingWidth,
        remainingHeight,
        totalValue
      );

      if (!rowInfo) break;

      const { endIndex, rowWidth, rowHeight, isVertical } = rowInfo;

      // Layout the row
      let x = currentX;
      let y = currentY;

      for (let i = startIndex; i < endIndex; i++) {
        const child = sortedChildren[i];
        const value = child.value || child.size || 1;
        const ratio = value / rowInfo.totalValue;

        let rectWidth, rectHeight;

        if (isVertical) {
          // Row is vertical (taller than wide)
          rectWidth = rowWidth;
          rectHeight = rowHeight * ratio;
        } else {
          // Row is horizontal (wider than tall)
          rectWidth = rowWidth * ratio;
          rectHeight = rowHeight;
        }

        rectangles.push({
          x: x,
          y: y,
          width: Math.max(1, rectWidth),
          height: Math.max(1, rectHeight),
        });

        if (isVertical) {
          y += rectHeight;
        } else {
          x += rectWidth;
        }
      }

      // Update layout position
      if (isVertical) {
        currentX += rowWidth;
        remainingWidth -= rowWidth;
      } else {
        currentY += rowHeight;
        remainingHeight -= rowHeight;
      }

      startIndex = endIndex;
    }

    // Map rectangles back to original order
    const result = new Array(children.length);
    sortedChildren.forEach((child, sortedIndex) => {
      const originalIndex = children.indexOf(child);
      result[originalIndex] = rectangles[sortedIndex];
    });

    return result;
  }

  // Find the best row of items for the squarified algorithm
  findBestRow(children, startIndex, availableWidth, availableHeight, totalValue) {
    if (startIndex >= children.length) return null;

    const totalArea = availableWidth * availableHeight;
    let bestRow = null;
    let bestRatio = Infinity;

    // Try different row sizes
    for (let endIndex = startIndex + 1; endIndex <= children.length; endIndex++) {
      const rowChildren = children.slice(startIndex, endIndex);
      const rowTotalValue = rowChildren.reduce(
        (sum, child) => sum + (child.value || child.size || 1),
        0
      );
      const rowArea = (rowTotalValue / totalValue) * totalArea;

      // Calculate row dimensions
      const aspectRatio = availableWidth / availableHeight;
      let rowWidth, rowHeight;

      if (aspectRatio > 1) {
        // Available space is wider than tall
        rowHeight = Math.sqrt(rowArea / aspectRatio);
        rowWidth = rowArea / rowHeight;
      } else {
        // Available space is taller than wide
        rowWidth = Math.sqrt(rowArea * aspectRatio);
        rowHeight = rowArea / rowWidth;
      }

      // Calculate worst aspect ratio in this row
      let worstRatio = 0;
      rowChildren.forEach((child) => {
        const value = child.value || child.size || 1;
        const itemArea = (value / rowTotalValue) * rowArea;

        let itemWidth, itemHeight;
        if (rowWidth > rowHeight) {
          itemWidth = (value / rowTotalValue) * rowWidth;
          itemHeight = rowHeight;
        } else {
          itemWidth = rowWidth;
          itemHeight = (value / rowTotalValue) * rowHeight;
        }

        const itemRatio = Math.max(itemWidth / itemHeight, itemHeight / itemWidth);
        worstRatio = Math.max(worstRatio, itemRatio);
      });

      // Keep track of the best row (lowest worst aspect ratio)
      if (worstRatio < bestRatio) {
        bestRatio = worstRatio;
        bestRow = {
          endIndex,
          rowWidth,
          rowHeight,
          totalValue: rowTotalValue,
          isVertical: rowHeight > rowWidth,
        };
      }

      // Stop if we've found a reasonably good row
      if (worstRatio < 2.0) break;
    }

    return bestRow;
  }
}

function generateSimilarColor(baseColor, range) {
  // Helper function to ensure a value is within 0-255
  const clamp = (value) => Math.min(255, Math.max(0, value));

  // Convert base color to RGB
  const baseRGB = hexToRGB(baseColor);

  // Generate new RGB values within the specified range
  const newRGB = baseRGB.map((value) => {
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
  return (
    '#' +
    rgb
      .map((x) => {
        const hex = x.toString(16);
        return hex.length === 1 ? '0' + hex : hex;
      })
      .join('')
  );
}
