import { Pipe, PipeTransform } from '@angular/core';

type ListType = 'ul' | 'ol' | null;

@Pipe({
  name: 'markdown',
  standalone: true,
})
export class MarkdownPipe implements PipeTransform {
  transform(value: string | null | undefined): string {
    return value ? renderMarkdown(value) : '';
  }
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function inline(text: string): string {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
}

// Renders the constrained markdown subset the diagnostic LLM is prompted to
// produce (headings, `1) Section` headers, bullet/numbered lists, bold/italic/code).
function renderMarkdown(source: string): string {
  const lines = source.replace(/\r\n/g, '\n').split('\n');
  const html: string[] = [];
  let listType: ListType = null;
  let paragraph: string[] = [];

  const closeList = (): void => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = null;
    }
  };

  const flushParagraph = (): void => {
    if (paragraph.length) {
      html.push(`<p>${paragraph.join(' ')}</p>`);
      paragraph = [];
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      flushParagraph();
      closeList();
      continue;
    }

    const hashHeading = line.match(/^(#{1,3})\s+(.*)$/);
    const sectionHeading = hashHeading ? null : line.match(/^(\d+)\)\s+(.*)$/);
    if (hashHeading || sectionHeading) {
      flushParagraph();
      closeList();
      const level = hashHeading ? hashHeading[1].length : 3;
      const text = hashHeading ? hashHeading[2] : `${sectionHeading![1]}) ${sectionHeading![2]}`;
      html.push(`<h${level}>${inline(text)}</h${level}>`);
      continue;
    }

    const bullet = line.match(/^[-*]\s+(.*)$/);
    if (bullet) {
      flushParagraph();
      if (listType !== 'ul') {
        closeList();
        html.push('<ul>');
        listType = 'ul';
      }
      html.push(`<li>${inline(bullet[1])}</li>`);
      continue;
    }

    const numbered = line.match(/^\d+\.\s+(.*)$/);
    if (numbered) {
      flushParagraph();
      if (listType !== 'ol') {
        closeList();
        html.push('<ol>');
        listType = 'ol';
      }
      html.push(`<li>${inline(numbered[1])}</li>`);
      continue;
    }

    closeList();
    paragraph.push(inline(line));
  }

  flushParagraph();
  closeList();
  return html.join('\n');
}
