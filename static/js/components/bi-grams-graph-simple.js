'use strict';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class BiGramsGraphSimple {
    constructor(containerSelector, tag, eventSystem) {
        this.containerSelector = containerSelector;
        this.tag = tag;
        this.ES = eventSystem;
        this.data = null;
        this.loaded = false;
    }

    fetchData() {
        rsstag_utils.fetchJSON(
            `/api/tag-bi-grams-graph/${encodeURIComponent(this.tag)}`,
            {
                method: 'GET',
                credentials: 'include',
                headers: {'Content-Type': 'application/json'}
            }
        ).then(response => {
            if (response.data) {
                this.data = response.data;
                this.renderSimpleVisualization();
            } else {
                console.error('No graph data received');
                this.renderError('No graph data available');
            }
        }).catch(error => {
            console.error('Error fetching bi-grams graph data:', error);
            this.renderError('Failed to load graph data');
        });
    }

    renderSimpleVisualization() {
        if (!this.data || !this.data.nodes || !this.data.links) {
            this.renderError('Invalid graph data');
            return;
        }

        // Clear previous content
        const container = document.querySelector(this.containerSelector);
        if (!container) {
            console.error('Container not found:', this.containerSelector);
            return;
        }
        container.innerHTML = '';

        // Create a simple table visualization as fallback
        const table = document.createElement('table');
        table.style.width = '100%';
        table.style.borderCollapse = 'collapse';
        table.style.marginTop = '10px';

        // Table header
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        
        const mainTagHeader = document.createElement('th');
        mainTagHeader.textContent = 'Main Tag';
        mainTagHeader.style.border = '1px solid #ddd';
        mainTagHeader.style.padding = '8px';
        mainTagHeader.style.backgroundColor = '#f2f2f2';
        mainTagHeader.style.textAlign = 'left';
        
        const relatedTagHeader = document.createElement('th');
        relatedTagHeader.textContent = 'Related Tag';
        relatedTagHeader.style.border = '1px solid #ddd';
        relatedTagHeader.style.padding = '8px';
        relatedTagHeader.style.backgroundColor = '#f2f2f2';
        relatedTagHeader.style.textAlign = 'left';
        
        const frequencyHeader = document.createElement('th');
        frequencyHeader.textContent = 'Frequency';
        frequencyHeader.style.border = '1px solid #ddd';
        frequencyHeader.style.padding = '8px';
        frequencyHeader.style.backgroundColor = '#f2f2f2';
        frequencyHeader.style.textAlign = 'left';
        
        headerRow.appendChild(mainTagHeader);
        headerRow.appendChild(relatedTagHeader);
        headerRow.appendChild(frequencyHeader);
        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Table body
        const tbody = document.createElement('tbody');
        
        // Find the main tag node
        const mainTagNode = this.data.nodes.find(node => node.id === this.tag);
        
        // Create rows for each connection
        this.data.links.forEach(link => {
            const row = document.createElement('tr');
            
            // Main tag cell
            const mainTagCell = document.createElement('td');
            mainTagCell.textContent = link.source;
            mainTagCell.style.border = '1px solid #ddd';
            mainTagCell.style.padding = '8px';
            if (link.source === this.tag) {
                mainTagCell.style.fontWeight = 'bold';
                mainTagCell.style.color = '#ff4500';
            }
            
            // Related tag cell
            const relatedTagCell = document.createElement('td');
            relatedTagCell.textContent = link.target;
            relatedTagCell.style.border = '1px solid #ddd';
            relatedTagCell.style.padding = '8px';
            if (link.target === this.tag) {
                relatedTagCell.style.fontWeight = 'bold';
                relatedTagCell.style.color = '#ff4500';
            }
            
            // Frequency cell
            const frequencyCell = document.createElement('td');
            frequencyCell.textContent = link.weight;
            frequencyCell.style.border = '1px solid #ddd';
            frequencyCell.style.padding = '8px';
            frequencyCell.style.textAlign = 'right';
            
            row.appendChild(mainTagCell);
            row.appendChild(relatedTagCell);
            row.appendChild(frequencyCell);
            tbody.appendChild(row);
        });
        
        table.appendChild(tbody);
        container.appendChild(table);
        
        // Add a note about the visualization
        const note = document.createElement('p');
        note.textContent = 'Note: This is a simple tabular representation. For full graph visualization, please ensure D3.js is properly loaded.';
        note.style.fontStyle = 'italic';
        note.style.color = '#666';
        note.style.marginTop = '10px';
        container.appendChild(note);
    }

    renderError(message) {
        const container = document.querySelector(this.containerSelector);
        if (!container) {
            console.error('Container not found:', this.containerSelector);
            return;
        }
        container.innerHTML = '';
        
        const errorDiv = document.createElement('div');
        errorDiv.textContent = message;
        errorDiv.style.color = '#d32f2f';
        errorDiv.style.padding = '10px';
        errorDiv.style.backgroundColor = '#ffebee';
        errorDiv.style.border = '1px solid #ef9a9a';
        errorDiv.style.borderRadius = '4px';
        errorDiv.style.margin = '10px 0';
        
        container.appendChild(errorDiv);
    }

    start() {
        if (this.loaded) {
            return;
        }
        this.loaded = true;
        this.fetchData();
    }
}