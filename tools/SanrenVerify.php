<?php
/** Verify page existence and exact wikitext equality without browser APIs. */
require_once '/var/www/html/maintenance/Maintenance.php';
class SanrenVerify extends Maintenance {
    public function execute() {
        $manifest = json_decode(file_get_contents('/build/pages.json'), true);
        $missing = [];
        $mismatch = [];
        $nsCounts = [];
        $services = MediaWiki\MediaWikiServices::getInstance();
        $lookup = $services->getPageStore()->newSelectQueryBuilder();
        foreach ($manifest as $page) {
            $title = MediaWiki\Title\Title::newFromText($page['title']);
            if (!$title || !$title->exists()) {
                $missing[] = $page['title'];
                continue;
            }
            $ns = $title->getNamespace();
            $nsCounts[$ns] = ($nsCounts[$ns] ?? 0) + 1;
            $content = $services->getRevisionLookup()->getRevisionByTitle($title)?->getContent('main');
            $expected = rtrim(str_replace(["\r\n", "\r"], "\n", file_get_contents('/build/pages/' . $page['file'])));
            $actual = rtrim(str_replace(["\r\n", "\r"], "\n", $content?->getText() ?? ''));
            if (!$content || $actual !== $expected) {
                $mismatch[] = $page['title'];
            }
        }
        $db = $this->getReplicaDB();
        $files = $db->newSelectQueryBuilder()->select('COUNT(*)')->from('image')->caller(__METHOD__)->fetchField();
        $result = ['manifest' => count($manifest), 'missing' => $missing, 'content_mismatch' => $mismatch,
                   'namespace_counts' => $nsCounts, 'imported_files' => (int)$files];
        file_put_contents('/build/verification.json', json_encode($result, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
        $this->output(json_encode($result, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n");
    }
}
$maintClass = SanrenVerify::class;
require_once RUN_MAINTENANCE_IF_MAIN;
