<?php
require_once '/var/www/html/maintenance/Maintenance.php';
class SanrenNamespaceFix extends Maintenance {
    public function execute() {
        $ns = (int)$this->getArg(0);
        $dbw = $this->getPrimaryDB();
        $total = 0;
        $last = 0;
        while (true) {
            $rows = $dbw->newSelectQueryBuilder()->select(['page_id','page_title'])
                ->from('page')->where(['page_namespace' => 0, "page_id > $last"])
                ->orderBy('page_id')->limit(200)->caller(__METHOD__)->fetchResultSet();
            if (!$rows->numRows()) break;
            foreach ($rows as $row) {
                $last = $row->page_id;
                $title = MediaWiki\Title\Title::newFromText($row->page_title);
                if ($title && $title->getNamespace() === $ns) {
                    $dbw->newUpdateQueryBuilder()->update('page')->set(['page_namespace' => $ns])
                        ->where(['page_id' => $row->page_id])->caller(__METHOD__)->execute();
                    $total++;
                }
            }
        }
        $this->output("Moved $total pages into namespace $ns\n");
    }
}
$maintClass = SanrenNamespaceFix::class;
require_once RUN_MAINTENANCE_IF_MAIN;
