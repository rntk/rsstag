/**
 * Shared Legend component for River Charts (Vanilla JS version)
 */
export default class RiverLegend {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? document.querySelector(container) : container;
        this.items = options.items || [];
        this.colorScale = options.colorScale;
        this.onActivate = options.onActivate || (() => { });
        this.activeItem = null;
        this.variant = options.variant || 'default';
    }

    update(activeItem) {
        this.activeItem = activeItem;
        this.render();
    }

    render() {
        if (!this.container || !this.items || this.items.length === 0) return;

        this.container.innerHTML = '';
        this.container.className = `river-legend river-legend-${this.variant}`;

        Object.assign(this.container.style, {
            marginTop: '15px',
            borderTop: '1px solid #eee',
            paddingTop: '15px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '8px',
            justifyContent: 'center'
        });

        this.items.forEach(item => {
            const name = item.name || item;
            const isActive = this.activeItem === name;
            const isDimmed = this.activeItem && this.activeItem !== name;

            const el = document.createElement('div');
            el.className = 'river-legend-item';

            Object.assign(el.style, {
                display: 'flex',
                alignItems: 'center',
                padding: this.variant === 'pill' ? '6px 12px' : '4px 8px',
                backgroundColor: isActive ? (this.variant === 'pill' ? '#eee' : '#f0f0f0') : (this.variant === 'pill' ? 'white' : 'transparent'),
                border: this.variant === 'pill' ? '1px solid #ddd' : 'none',
                borderRadius: this.variant === 'pill' ? '20px' : '4px',
                cursor: 'pointer',
                transition: 'all 0.2s',
                opacity: isDimmed ? 0.4 : 1,
                boxShadow: isActive && this.variant === 'pill' ? '0 2px 4px rgba(0,0,0,0.1)' : 'none'
            });

            const colorBox = document.createElement('div');
            Object.assign(colorBox.style, {
                width: '12px',
                height: '12px',
                backgroundColor: this.colorScale(name),
                borderRadius: this.variant === 'pill' ? '50%' : '2px',
                marginRight: '8px'
            });

            const label = document.createElement('span');
            label.textContent = name;
            Object.assign(label.style, {
                fontSize: '12px',
                fontWeight: this.variant === 'pill' ? '500' : 'normal',
                color: '#333'
            });

            el.appendChild(colorBox);
            el.appendChild(label);

            el.addEventListener('mouseenter', () => this.onActivate(name));
            el.addEventListener('mouseleave', () => this.onActivate(null));

            this.container.appendChild(el);
        });
    }
}
