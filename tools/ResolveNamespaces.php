<?php
/** Resolve namespaces offline; no HTTP or external services. */
require_once '/var/www/html/maintenance/Maintenance.php';
class SanrenNamespaces extends Maintenance {
    public function execute() {
        $manifest = json_decode(file_get_contents('/build/pages.json'), true);
        $counts = [];
        foreach ($manifest as &$page) {
            $title = MediaWiki\Title\Title::newFromText($page['title']);
            if (!$title) {
                fwrite(STDERR, 'Invalid title: ' . $page['title'] . "\n");
                exit(1);
            }
            $ns = $title->getNamespace();
            $page['ns'] = $ns;
            $page['content_model'] = 'wikitext';
            $counts[$ns] = ($counts[$ns] ?? 0) + 1;
        }
        file_put_contents('/build/pages.json', json_encode($manifest, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
        $this->output(json_encode($counts, JSON_UNESCAPED_UNICODE) . "\n");
    }
}
$maintClass = SanrenNamespaces::class;
require_once RUN_MAINTENANCE_IF_MAIN;
