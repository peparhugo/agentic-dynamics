def test_cs3_trivial_mount_proof():
    import os, pathlib
    assert pathlib.Path('/repo/.git').is_dir(), 'clone .git must be present'
    assert pathlib.Path('/repo/experiments/results/smoke/fleet_launch_container_smoke/cs3_smoke_cell.yaml').is_file()
    assert pathlib.Path('/repo/experiments/results/smoke/fleet_launch_container_smoke/test_cs3_smoke_cell.py').is_file()
    try:
        open('/repo/.cs3_ro_probe', 'w').close()
    except OSError:
        pass
    else:
        os.remove('/repo/.cs3_ro_probe')
        raise AssertionError('/repo is writable - expected read-only clone mount')
