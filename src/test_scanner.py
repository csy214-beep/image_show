import os


def count_all_files(folder_path):
    """
    统计指定文件夹下所有文件的数量（包括子文件夹）

    参数:
        folder_path (str): 目标文件夹的路径

    返回:
        int: 文件的总数量；如果发生错误，返回-1
    """
    # 初始化文件数量计数器
    file_count = 0

    # 检查路径是否存在
    if not os.path.exists(folder_path):
        print(f"错误：路径 '{folder_path}' 不存在！")
        return -1

    # 检查路径是否是文件夹
    if not os.path.isdir(folder_path):
        print(f"错误：'{folder_path}' 不是一个文件夹！")
        return -1

    try:
        # os.walk() 会递归遍历文件夹及其所有子文件夹
        # root: 当前遍历的目录路径
        # dirs: 当前目录下的子文件夹列表
        # files: 当前目录下的文件列表
        for root, dirs, files in os.walk(folder_path):
            # 累加当前目录下的文件数量
            file_count += len(files)
    except PermissionError:
        print(f"错误：没有权限访问 '{folder_path}' 或其子文件夹！")
        return -1
    except Exception as e:
        print(f"未知错误：{e}")
        return -1

    return file_count


# 测试函数（替换为你要统计的文件夹路径）
if __name__ == "__main__":
    target_folder = "D:/Users/Pfolg/Pictures/pixiv_scripts/pixiv"
    total_files = count_all_files(target_folder)
    if total_files >= 0:
        print(f"文件夹 '{target_folder}' 下的文件总数：{total_files}")
