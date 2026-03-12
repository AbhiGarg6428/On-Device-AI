from tools.control_pc import control_pc


def run(command):
    result = control_pc(command)

    if result:
        return result

    return None