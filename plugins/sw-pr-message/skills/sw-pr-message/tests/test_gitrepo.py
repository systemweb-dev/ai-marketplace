def test_repo_novo_nasce_em_master_com_um_commit(repo):
    assert repo.git("branch", "--show-current").strip() == "master"
    assert repo.git("rev-list", "--count", "HEAD").strip() == "1"


def test_ref_remota_e_origin_head_sem_rede(repo):
    repo.ref_remota("master")
    repo.origin_head("master")

    assert repo.git("symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip() == "origin/master"
