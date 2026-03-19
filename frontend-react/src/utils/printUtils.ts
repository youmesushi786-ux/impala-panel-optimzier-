export function printCurrentPage() {
  window.print();
}

export function printElementById(elementId: string, title?: string) {
  const content = document.getElementById(elementId);

  if (!content) {
    throw new Error(`Element with id "${elementId}" not found`);
  }

  const printWindow = window.open('', '_blank', 'width=1200,height=900');

  if (!printWindow) {
    throw new Error('Unable to open print window. Please allow popups for this site.');
  }

  const styles = Array.from(
    document.querySelectorAll('style, link[rel="stylesheet"]')
  )
    .map((node) => node.outerHTML)
    .join('\n');

  printWindow.document.open();
  printWindow.document.write(`
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>${title || 'Print'}</title>
        ${styles}
        <style>
          body {
            font-family: Arial, Helvetica, sans-serif;
            padding: 20px;
            margin: 0;
            color: #000;
            background: #fff;
          }

          .no-print {
            display: none !important;
          }

          .print-root {
            width: 100%;
          }
        </style>
      </head>
      <body>
        <div class="print-root">
          ${content.outerHTML}
        </div>
      </body>
    </html>
  `);
  printWindow.document.close();

  printWindow.focus();

  setTimeout(() => {
    printWindow.print();
    printWindow.close();
  }, 600);
}

export function printHtmlContent(html: string, title?: string) {
  const printWindow = window.open('', '_blank', 'width=1200,height=900');

  if (!printWindow) {
    throw new Error('Unable to open print window. Please allow popups for this site.');
  }

  const styles = Array.from(
    document.querySelectorAll('style, link[rel="stylesheet"]')
  )
    .map((node) => node.outerHTML)
    .join('\n');

  printWindow.document.open();
  printWindow.document.write(`
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>${title || 'Print'}</title>
        ${styles}
        <style>
          body {
            font-family: Arial, Helvetica, sans-serif;
            padding: 20px;
            margin: 0;
            color: #000;
            background: #fff;
          }

          .no-print {
            display: none !important;
          }
        </style>
      </head>
      <body>
        ${html}
      </body>
    </html>
  `);
  printWindow.document.close();

  printWindow.focus();

  setTimeout(() => {
    printWindow.print();
    printWindow.close();
  }, 600);
}