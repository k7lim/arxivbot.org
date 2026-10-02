function goToPaper(event) {
    event.preventDefault();
    const input = document.getElementById('paper-input').value.trim();

    // Extract arXiv ID from various formats
    let paperId = input;

    // Handle full URLs (arxiv.org, arxivbot.org, ar5iv.org)
    const urlMatch = input.match(/(?:arxiv|arxivbot|ar5iv)(?:\.labs)?\.org\/(?:abs|pdf|html)\/([^\s\/]+)/);
    if (urlMatch) {
        paperId = urlMatch[1].replace('.pdf', '');
    }

    // Handle arxiv: prefix
    if (paperId.startsWith('arxiv:')) {
        paperId = paperId.substring(6);
    }

    if (paperId) {
        window.location.href = '/old/abs/' + paperId;
    }
    return false;
}
