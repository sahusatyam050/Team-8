// API Configuration
const API_URL = 'http://localhost:8000';

// DOM Elements - Mode Switcher
const modeBtns = document.querySelectorAll('.mode-btn');
const ragMode = document.getElementById('rag-mode');
const scrapeMode = document.getElementById('scrape-mode');

// DOM Elements - RAG Mode
const indexForm = document.getElementById('indexForm');
const indexUrlInput = document.getElementById('indexUrlInput');
const indexBtn = document.getElementById('indexBtn');
const indexedSourcesList = document.getElementById('indexedSourcesList');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const chatMessages = document.getElementById('chatMessages');

// DOM Elements - Scrape Mode
const scrapeForm = document.getElementById('scrapeForm');
const urlInput = document.getElementById('urlInput');
const scrapeBtn = document.getElementById('scrapeBtn');
const loading = document.getElementById('loading');
const errorMessage = document.getElementById('errorMessage');
const resultsSection = document.getElementById('resultsSection');
const exampleButtons = document.querySelectorAll('.example-btn');
const tabButtons = document.querySelectorAll('.tab-btn');

// Mode Switching
modeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const mode = btn.dataset.mode;

        // Update active mode button
        modeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update active mode content
        if (mode === 'rag') {
            ragMode.classList.add('active');
            scrapeMode.classList.remove('active');
            loadIndexedSources();
        } else {
            ragMode.classList.remove('active');
            scrapeMode.classList.add('active');
        }
    });
});

// ============= RAG MODE FUNCTIONS =============

// Load Indexed Sources
async function loadIndexedSources() {
    try {
        const response = await fetch(`${API_URL}/indexed-sources`);
        const data = await response.json();

        if (data.success && data.sources.length > 0) {
            displayIndexedSources(data.sources);
        } else {
            indexedSourcesList.innerHTML = '<div class="empty-state">No sources indexed yet</div>';
        }
    } catch (error) {
        console.error('Failed to load sources:', error);
    }
}

// Display Indexed Sources
function displayIndexedSources(sources) {
    indexedSourcesList.innerHTML = '';

    sources.forEach(source => {
        const div = document.createElement('div');
        div.className = 'source-item';
        div.innerHTML = `
            <div class="source-info">
                <div class="source-title">${escapeHtml(source.title)}</div>
                <div class="source-url">${escapeHtml(source.url)}</div>
                <div class="source-chunks">${source.chunks} chunks</div>
            </div>
            <button class="delete-source-btn" data-url="${escapeHtml(source.url)}">Delete</button>
        `;

        // Add delete handler
        div.querySelector('.delete-source-btn').addEventListener('click', () => {
            deleteSource(source.url);
        });

        indexedSourcesList.appendChild(div);
    });
}

// Index Website
indexForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const url = indexUrlInput.value.trim();
    if (!url) return;

    try {
        indexBtn.disabled = true;
        indexBtn.textContent = 'Indexing...';

        const response = await fetch(`${API_URL}/scrape-and-index`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });

        const data = await response.json();

        if (data.success) {
            // Add success message to chat
            addChatMessage('system', `✅ Successfully indexed: ${data.data.title} (${data.data.chunks_indexed} chunks)`);

            // Reload sources
            loadIndexedSources();

            // Clear input
            indexUrlInput.value = '';
        } else {
            addChatMessage('error', `Failed to index: ${data.error}`);
        }

    } catch (error) {
        addChatMessage('error', `Error: ${error.message}`);
    } finally {
        indexBtn.disabled = false;
        indexBtn.textContent = '📥 Index Website';
    }
});

// Delete Source
async function deleteSource(sourceUrl) {
    if (!confirm('Are you sure you want to remove this source?')) return;

    try {
        const response = await fetch(`${API_URL}/delete-source?source_url=${encodeURIComponent(sourceUrl)}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            addChatMessage('system', `🗑️ Removed source from index`);
            loadIndexedSources();
        } else {
            addChatMessage('error', `Failed to delete: ${data.error}`);
        }
    } catch (error) {
        addChatMessage('error', `Error: ${error.message}`);
    }
}

// Chat Query
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const question = chatInput.value.trim();
    if (!question) return;

    // Add user message
    addChatMessage('user', question);

    // Clear input
    chatInput.value = '';

    // Add loading message
    const loadingId = addChatMessage('loading', 'Thinking...');

    try {
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: question,
                n_results: 5
            })
        });

        const data = await response.json();

        // Remove loading message
        removeChatMessage(loadingId);

        if (data.success) {
            addChatMessage('assistant', data.answer, data.sources);
        } else {
            addChatMessage('error', data.error);
        }

    } catch (error) {
        removeChatMessage(loadingId);
        addChatMessage('error', `Failed to query: ${error.message}`);
    }
});

// Add Chat Message
function addChatMessage(type, content, sources = null) {
    const messageId = `msg-${Date.now()}`;
    const div = document.createElement('div');
    div.className = 'chat-message';
    div.id = messageId;

    if (type === 'user') {
        div.innerHTML = `<div class="message-user">${escapeHtml(content)}</div>`;
    } else if (type === 'assistant') {
        let sourcesHtml = '';
        if (sources && sources.length > 0) {
            sourcesHtml = `
                <div class="message-sources">
                    <div class="source-label">Sources:</div>
                    <div class="source-links">
                        ${sources.map(s => `
                            <a href="${s.url}" target="_blank" rel="noopener" class="source-link">
                                ${escapeHtml(s.title || s.url)}
                            </a>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        div.innerHTML = `
            <div class="message-assistant">
                <div class="answer-text">${formatMarkdown(content)}</div>
                ${sourcesHtml}
            </div>
        `;
    } else if (type === 'error') {
        div.innerHTML = `<div class="message-error">❌ ${escapeHtml(content)}</div>`;
    } else if (type === 'system') {
        div.innerHTML = `<div class="message-assistant">${escapeHtml(content)}</div>`;
    } else if (type === 'loading') {
        div.innerHTML = `
            <div class="message-loading">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
                <span>${escapeHtml(content)}</span>
            </div>
        `;
    }

    // Remove welcome message if present
    const welcome = chatMessages.querySelector('.welcome-message');
    if (welcome) {
        welcome.remove();
    }

    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return messageId;
}

// Remove Chat Message
function removeChatMessage(messageId) {
    const msg = document.getElementById(messageId);
    if (msg) msg.remove();
}

// Format Markdown (basic)
function formatMarkdown(text) {
    // Convert newlines to <br>
    text = text.replace(/\n/g, '<br>');

    // Bold **text**
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Italic *text*
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Code `text`
    text = text.replace(/`(.*?)`/g, '<code>$1</code>');

    return text;
}

// ============= SCRAPE MODE FUNCTIONS =============

// Example URL Buttons
exampleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        urlInput.value = btn.dataset.url;
        urlInput.focus();
    });
});

// Tab Switching
tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.dataset.tab;

        // Update active tab button
        tabButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update active tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabName}-tab`).classList.add('active');
    });
});

// Form Submission
scrapeForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const url = urlInput.value.trim();
    if (!url) return;

    await scrapeWebsite(url);
});

// Main Scraping Function
async function scrapeWebsite(url) {
    try {
        // Show loading, hide error and results
        loading.classList.add('active');
        errorMessage.classList.remove('active');
        resultsSection.classList.remove('active');
        scrapeBtn.disabled = true;

        // Make API request
        const response = await fetch(`${API_URL}/scrape`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to scrape website');
        }

        if (data.success) {
            displayResults(data.data);
        } else {
            throw new Error(data.error || 'Unknown error occurred');
        }

    } catch (error) {
        showError(error.message);
    } finally {
        loading.classList.remove('active');
        scrapeBtn.disabled = false;
    }
}

// Display Results
function displayResults(data) {
    // Display statistics
    displayStats(data.stats);

    // Display metadata
    displayMetadata(data.metadata);

    // Display headings
    displayHeadings(data.text.headings);

    // Display paragraphs
    displayParagraphs(data.text.paragraphs);

    // Display images
    displayImages(data.images);

    // Display links
    displayLinks(data.links);

    // Display tables
    displayTables(data.tables);

    // Show results section
    resultsSection.classList.add('active');

    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Display Statistics
function displayStats(stats) {
    const statsGrid = document.getElementById('statsGrid');
    statsGrid.innerHTML = `
        <div class="stat-card">
            <span class="stat-value">${stats.total_headings}</span>
            <span class="stat-label">Headings</span>
        </div>
        <div class="stat-card">
            <span class="stat-value">${stats.total_paragraphs}</span>
            <span class="stat-label">Paragraphs</span>
        </div>
        <div class="stat-card">
            <span class="stat-value">${stats.total_images}</span>
            <span class="stat-label">Images</span>
        </div>
        <div class="stat-card">
            <span class="stat-value">${stats.total_links}</span>
            <span class="stat-label">Links</span>
        </div>
        <div class="stat-card">
            <span class="stat-value">${stats.total_tables}</span>
            <span class="stat-label">Tables</span>
        </div>
    `;
}

// Display Metadata
function displayMetadata(metadata) {
    const metadataContent = document.getElementById('metadataContent');
    metadataContent.innerHTML = '';

    const metadataItems = [
        { label: 'Title', value: metadata.title || 'N/A' },
        { label: 'Description', value: metadata.description || 'N/A' },
        { label: 'Keywords', value: metadata.keywords || 'N/A' },
        { label: 'Author', value: metadata.author || 'N/A' }
    ];

    metadataItems.forEach(item => {
        const div = document.createElement('div');
        div.className = 'metadata-item';
        div.innerHTML = `
            <div class="metadata-label">${item.label}</div>
            <div class="metadata-value">${escapeHtml(item.value)}</div>
        `;
        metadataContent.appendChild(div);
    });
}

// Display Headings
function displayHeadings(headings) {
    const headingsContent = document.getElementById('headingsContent');
    headingsContent.innerHTML = '';

    let hasHeadings = false;

    for (let level = 1; level <= 6; level++) {
        const key = `h${level}`;
        const items = headings[key];

        if (items && items.length > 0) {
            hasHeadings = true;
            const div = document.createElement('div');
            div.className = 'heading-group';

            const title = document.createElement('h3');
            title.textContent = `Heading ${level}`;
            div.appendChild(title);

            const ul = document.createElement('ul');
            items.forEach(item => {
                const li = document.createElement('li');
                li.textContent = item;
                ul.appendChild(li);
            });
            div.appendChild(ul);

            headingsContent.appendChild(div);
        }
    }

    if (!hasHeadings) {
        headingsContent.innerHTML = '<div class="empty-state">No headings found</div>';
    }
}

// Display Paragraphs
function displayParagraphs(paragraphs) {
    const paragraphsContent = document.getElementById('paragraphsContent');
    paragraphsContent.innerHTML = '';

    if (paragraphs && paragraphs.length > 0) {
        // Limit to first 50 paragraphs to avoid overwhelming the UI
        const displayParagraphs = paragraphs.slice(0, 50);

        displayParagraphs.forEach(para => {
            const div = document.createElement('div');
            div.className = 'paragraph-item';
            div.textContent = para;
            paragraphsContent.appendChild(div);
        });

        if (paragraphs.length > 50) {
            const note = document.createElement('div');
            note.className = 'empty-state';
            note.textContent = `Showing first 50 of ${paragraphs.length} paragraphs`;
            paragraphsContent.appendChild(note);
        }
    } else {
        paragraphsContent.innerHTML = '<div class="empty-state">No paragraphs found</div>';
    }
}

// Display Images
function displayImages(images) {
    const imagesContent = document.getElementById('imagesContent');
    imagesContent.innerHTML = '';

    if (images && images.length > 0) {
        images.forEach(img => {
            const div = document.createElement('div');
            div.className = 'image-item';

            const imgEl = document.createElement('img');
            imgEl.src = img.url;
            imgEl.alt = img.alt || 'Image';
            imgEl.onerror = function () {
                this.style.display = 'none';
                const errorMsg = document.createElement('div');
                errorMsg.style.padding = '2rem';
                errorMsg.style.textAlign = 'center';
                errorMsg.style.color = 'var(--text-muted)';
                errorMsg.textContent = 'Failed to load image';
                this.parentElement.appendChild(errorMsg);
            };

            div.appendChild(imgEl);

            const info = document.createElement('div');
            info.className = 'image-info';
            info.innerHTML = `
                <div class="image-alt">${escapeHtml(img.alt || 'No alt text')}</div>
                <div class="image-url">${escapeHtml(img.url)}</div>
            `;
            div.appendChild(info);

            imagesContent.appendChild(div);
        });
    } else {
        imagesContent.innerHTML = '<div class="empty-state">No images found</div>';
    }
}

// Display Links
function displayLinks(links) {
    displayLinksList(links.internal, 'internalLinksContent');
    displayLinksList(links.external, 'externalLinksContent');
}

function displayLinksList(linkArray, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';

    if (linkArray && linkArray.length > 0) {
        // Limit to first 100 links
        const displayLinks = linkArray.slice(0, 100);

        displayLinks.forEach(link => {
            const div = document.createElement('div');
            div.className = 'link-item';

            const textDiv = document.createElement('div');
            textDiv.style.flex = '1';
            textDiv.innerHTML = `
                <div class="link-text">${escapeHtml(link.text || 'No text')}</div>
                <div class="link-url">${escapeHtml(link.url)}</div>
            `;

            const visitBtn = document.createElement('a');
            visitBtn.href = link.url;
            visitBtn.target = '_blank';
            visitBtn.rel = 'noopener noreferrer';
            visitBtn.className = 'link-visit';
            visitBtn.textContent = 'Visit →';

            div.appendChild(textDiv);
            div.appendChild(visitBtn);
            container.appendChild(div);
        });

        if (linkArray.length > 100) {
            const note = document.createElement('div');
            note.className = 'empty-state';
            note.textContent = `Showing first 100 of ${linkArray.length} links`;
            container.appendChild(note);
        }
    } else {
        container.innerHTML = '<div class="empty-state">No links found</div>';
    }
}

// Display Tables
function displayTables(tables) {
    const tablesContent = document.getElementById('tablesContent');
    tablesContent.innerHTML = '';

    if (tables && tables.length > 0) {
        tables.forEach((tableData, index) => {
            const wrapper = document.createElement('div');
            wrapper.className = 'table-wrapper';

            const table = document.createElement('table');

            // Add headers if available
            if (tableData.headers && tableData.headers.length > 0) {
                const thead = document.createElement('thead');
                const headerRow = document.createElement('tr');

                tableData.headers.forEach(header => {
                    const th = document.createElement('th');
                    th.textContent = header;
                    headerRow.appendChild(th);
                });

                thead.appendChild(headerRow);
                table.appendChild(thead);
            }

            // Add rows
            if (tableData.rows && tableData.rows.length > 0) {
                const tbody = document.createElement('tbody');

                tableData.rows.forEach(row => {
                    const tr = document.createElement('tr');

                    row.forEach(cell => {
                        const td = document.createElement('td');
                        td.textContent = cell;
                        tr.appendChild(td);
                    });

                    tbody.appendChild(tr);
                });

                table.appendChild(tbody);
            }

            wrapper.appendChild(table);
            tablesContent.appendChild(wrapper);
        });
    } else {
        tablesContent.innerHTML = '<div class="empty-state">No tables found</div>';
    }
}

// Show Error
function showError(message) {
    errorMessage.textContent = `Error: ${message}`;
    errorMessage.classList.add('active');
    resultsSection.classList.remove('active');
}

// Utility: Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============= INITIALIZATION =============

// Check API Health on Load
window.addEventListener('load', async () => {
    try {
        const response = await fetch(`${API_URL}/health`);
        const data = await response.json();

        if (!response.ok) {
            addChatMessage('error', 'Backend server is not running. Please start the server first.');
        } else {
            if (!data.groq_api_configured) {
                addChatMessage('system', '⚠️ Groq API key not configured. RAG queries will not work. Please set GROQ_API_KEY in backend/.env');
            }
        }

        // Load indexed sources if in RAG mode
        loadIndexedSources();
    } catch (error) {
        addChatMessage('error', 'Cannot connect to backend server. Please ensure the server is running at http://localhost:8000');
    }
});
