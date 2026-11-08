<?php
require_once '/var/www/html/maintenance/Maintenance.php';
class SanrenRawModel extends Maintenance {
    public function execute() {
        $ns = (int)$this->getArg(0);
        $dbw = $this->getPrimaryDB();
        $dbw->newUpdateQueryBuilder()->update('page')->set(['page_content_model' => 'wikitext'])
            ->where(['page_namespace' => $ns])->caller(__METHOD__)->execute();
        $modelId = $dbw->newSelectQueryBuilder()->select('model_id')->from('content_models')
            ->where(['model_name' => 'wikitext'])->caller(__METHOD__)->fetchField();
        if (!$modelId) throw new RuntimeException('wikitext model not registered');
        $dbw->newUpdateQueryBuilder()->update('content')->set(['content_model' => $modelId])
            ->where('content_id IN (SELECT slot_content_id FROM slots JOIN revision ON slot_revision_id=rev_id JOIN page ON rev_page=page_id WHERE page_namespace=' . $ns . ')')->caller(__METHOD__)->execute();
        $this->output("Set namespace $ns to wikitext\n");
    }
}
$maintClass = SanrenRawModel::class;
require_once RUN_MAINTENANCE_IF_MAIN;
