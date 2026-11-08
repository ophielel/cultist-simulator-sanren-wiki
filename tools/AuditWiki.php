<?php
/** Audit the current local wiki against the generated page manifest. */
require_once '/var/www/html/maintenance/Maintenance.php';
class SanrenAudit extends Maintenance {
    public function execute() {
        $manifest = json_decode(file_get_contents('/build/pages.json'), true);
        $missing = [];
        $namespaces = [];
        foreach ($manifest as $page) {
            $title = MediaWiki\Title\Title::newFromText($page['title']);
            if (!$title || !$title->exists()) {
                $missing[] = $page['title'];
                continue;
            }
            $ns = $title->getNamespace();
            $namespaces[$ns] = ($namespaces[$ns] ?? 0) + 1;
        }
        $services = MediaWiki\MediaWikiServices::getInstance();
        $files = $services->getRepoGroup()->getLocalRepo()->getFileCount();
        $this->output(json_encode([
            'manifest_pages' => count($manifest),
            'missing_pages' => $missing,
            'namespaces' => $namespaces,
            'local_files' => $files,
        ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n");
    }
}
$maintClass = SanrenAudit::class;
require_once RUN_MAINTENANCE_IF_MAIN;
