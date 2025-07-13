"""
创建股票watch list的脚本
"""

import pickle
import os

def create_watchlist():
    """创建包含指定股票的watch list"""
    watchlist = ['NFLX', 'WMT', 'TSLA', 'GOOG', 'AMD', 'CNA.L', 'UBER', 'NIO']
    
    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    watchlist_path = os.path.join(script_dir, 'watchlist.pkl')
    
    # 保存为pickle文件
    with open(watchlist_path, 'wb') as f:
        pickle.dump(watchlist, f)
    
    print(f"Watch list已创建，包含以下股票: {watchlist}")
    print(f"文件保存位置: {watchlist_path}")
    return watchlist

if __name__ == "__main__":
    create_watchlist() 