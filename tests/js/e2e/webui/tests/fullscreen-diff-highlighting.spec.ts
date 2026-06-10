import { test, expect } from "../fixtures";

test.describe("Fullscreen Monaco Diff Highlighting", () => {
  test("diff content has syntax highlighting in fullscreen editor", async ({ page }) => {
    const result = await page.evaluate(() => {
      const vibeClient = (window as any).vibeClient;
      if (!vibeClient || !vibeClient.showCodeFullscreen) {
        return { error: 'showCodeFullscreen not available' };
      }

      const diffContent = [
        'diff --git a/test.py b/test.py',
        'index 1234567..abcdefg 100644',
        '--- a/test.py',
        '+++ b/test.py',
        '@@ -1,3 +1,3 @-',
        ' context line',
        '-old line',
        '+new line',
      ].join('\n');

      vibeClient.showCodeFullscreen('git diff', diffContent, 'diff');

      return new Promise<any>((resolve) => {
        setTimeout(() => {
          const monaco = (window as any).monaco;
          if (!monaco) {
            resolve({ error: 'monaco not loaded' });
            return;
          }

          const editor = vibeClient.currentEditor;
          const modelLang = editor?.getModel()?.getLanguageId?.() || 'unknown';

          const monacoContainer = vibeClient.monacoContainer;
          const containerHTML = monacoContainer?.innerHTML || '';

          // Monaco token span classes (mtk*) — multiple = tokenizer is working
          const mtkMatches = containerHTML.match(/mtk\d+/g);
          const uniqueMtkClasses = mtkMatches ? [...new Set(mtkMatches)] : [];
          const hasMultipleTokens = uniqueMtkClasses.length > 1;

          resolve({
            editorLanguage: modelLang,
            uniqueMtkClasses,
            hasMultipleTokens,
            containerHTMLLength: containerHTML.length,
          });
        }, 3000);
      });
    });

    expect(result.error).toBeUndefined();
    expect(result.editorLanguage).toBe('diff');
    expect(result.hasMultipleTokens).toBe(true);
  });
});
