# -*- coding: utf-8 -*-
"""
cea4py

oringinal author: ina111
http://qiita.com/ina111/items/f5c4eb35a848fdca04b8

Aug 27 2015 updated by rkanai
 - CEAのinputファイル作成部を汎用性が高いものに変更
 - CEAの出力を使って，適正でない膨張の時の補正を計算するようにした
 - iacとfacで関数を分離

実装済み関数
def cea_fac (OF, Pc, AR, CR, Pa = 0.101325):
 - エンジンの諸値から燃焼時の理論値を得る
 - AR = Area Ratio (A_exit / A_throat)
 - CR = Contraction Ratio (A_chamber / A_throat)
 - Pa = Pressure of ambient
 - 返り値はリスト [Pc, OF, isp, ivac, AR, cf]
 - 圧力の単位はMPaA，Ispの単位はsec，あとは無次元
 - fac(有限体積燃焼室)を仮定しているのでCRが引数に含まれる

実装予定
def cea_iac (OF, Pc, AR, Pa = 0.101325):
 - エンジンの諸値から燃焼時の理論値を得る
 - iac(無限体積燃焼室)を仮定しているのでCRは考慮しない
 - 他は cea_fac と同じ

実装したい
def cea_optexp_iac (OF, Pc, Pa = 0.101325)
 - あるO/FとPcにおける，最適膨張の開口比とその時の理論値を得る
 - 出口大気圧はデフォルト1atmを想定しているが，引数で変更可能
 - 返り値はリスト [isp, ivac, cf, aeat]


"""

import sys
reload(sys)
# デフォルトの文字コードを変更する．
sys.setdefaultencoding('utf-8')
import platform
import numpy as np
import os
import subprocess

# 以下のモジュールはテストの時しか使わない
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.font_manager import FontProperties
import csv


# 環境によって都度変更のこと
if 'Windows' == platform.system():
    cmd = 'C:\\CEA\\fCEA2.exe'

if 'Darwin' == platform.system():
    cmd = '~/Applications/NASAcea/FCEA2'

# 燃料の選択
fuel = 'C10H21,n-decyl'
fuel_temperature = 300

# CEA を python の関数として扱う．fac仮定
def cea_fac (OF, Pc, AR, CR, pa = 0.101325):
    file_name = 'ceatemp' # 一時的に作られるファイル

    # ---- .inpファイル作り ----
    input_file = file_name + '.inp'
    str = """problem    o/f=%.2f,
        rocket  equilibrium fac frozen  nfz=3
      p,bar = %.1f
      sup,ae/at= %.3f, ac/at = %.3f

    react  
      fuel=%s　wt=100 t,k=%d
      oxid=O2(L) wt=100  t,k=90.17
    output  
        plot p ispfz ivacfz cffz
    end
    """ % (OF, Pc*10, AR, CR, fuel, fuel_temperature)
# fac オプションを付けると出力は inj, chamber, throat, exit の順になる．
# exit の指定は出口圧力比(pi/p)，開口比(suparまたはsup,ae/at)などの方法があり，複数指定すると
# exit の出力も複数になるが，ここではある決まった(作った)ノズルに対する性能を見たいので開口比で指定．
# CR はac/at オプションで指定．
# 元記事同様，plotファイルから数字を読み出すがispやcfなどは末尾にfzを付けないとfrozen条件の値ではなく
# equilibrium 条件の値が出力されてしまうので注意．

    f = open(input_file, 'w') # 書き込みモードで開く
    f.write(str) # 引数の文字列をファイルに書き込む
    f.close() # ファイルを閉じる

# CEA実行ファイルへのパスを示す文字列cmdは冒頭のimport後に定義している
    p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
# さっき作った.inp ファイルの，".inp"を除いたファイル名をCEAの標準入力に渡す
# なぜ argv で渡せるようにしてくれなかったのか
    if 'Windows' == platform.system():
        p.communicate(file_name + '\n') # Win環境ではコマンド末尾に¥nを付けないとバグる
    if 'Darwin' == platform.system():
        p.communicate(file_name)

    # ---- .pltファイル読み取り ----
    output_file = file_name + '.plt'

    with open(output_file, 'r') as f:
        reader = csv.reader(f, delimiter=' ')
        header = next(reader)  # ヘッダーの読み飛ばし

        index = 0
        for row in reader:
            while row.count("") > 0:
                row.remove("")
            # print row          # 1行づつlist表示
            if index == 3:    # インジェクタ，チャンバ，スロートときてノズル出口は4行目
                p = float(row[0])
                isp_opt = float(row[1])
                ivac = float(row[2])
                cf_opt = float(row[3])
				# CEA は開口比を与えた時には大気圧によらず最適膨張(= 圧力推力なし)を仮定して
				# Ispやcfを出してくる．従って，「ある大気圧下での性能(海面高度含む)」を知りたい時は
				# 圧力推力項を加減してやる必要がある．それが以下の3式．教科書通り．
                cf = cf_opt + AR / Pc * (p/10 - pa)
                cf = max(0, cf)
                isp = isp_opt * cf / cf_opt
            index += 1
        data = [Pc, OF, isp, ivac, AR, cf]

    # ファイル削除
    os.remove(input_file)
    os.remove(output_file)

    return data





if __name__ == '__main__': # テスト用．これ以降がなくても他ファイルからモジュールとして関数は呼べる
    # とりあえず Isp vs AR のグラフを出力してみます
    vsar_data_file = 'csvfac_ispvsar.csv'
    vspc_data_file = 'csvfac_ispvspc.csv'
    vsof_data_file = 'csvfac_ispvsof.csv'
    vspa_data_file = 'csvfac_ispvspa.csv'

    if 'Windows' == platform.system():
        fp = FontProperties(fname=r'C:\WINDOWS\Fonts\ipaexg.ttf') # ipaゴシック好き フリーだしおすすめです

    if 'Darwin' == platform.system(): # for Mac
        font_path = '/Library/Fonts/Osaka.ttf'
        font_prop = matplotlib.font_manager.FontProperties(fname=font_path)
        fp = matplotlib.font_manager.FontProperties(fname=font_path)
        matplotlib.rcParams['font.family'] = font_prop.get_name()
        # pdfのフォントをTrueTypeに変更
        matplotlib.rcParams['pdf.fonttype'] = 42
        # defaultのdpi=100から変更
        matplotlib.rcParams['savefig.dpi'] = 300
        # 数式（Latex)のフォントを変更
        matplotlib.rcParams['mathtext.default'] = 'regular'
    plt.figure()

    # ---- パラメータ指定 ----
    pc_array1 = np.linspace(0.5, 8.5, 5) # 適っ当にPc=1, 3, 5, 7MPa
    ar_array1 = np.linspace(1.01, 10, 100) # ARは適っ当に2から10までを50分割してみる
    vsar_data_array = np.zeros((len(ar_array1), 6))
    save_array = np.zeros([1,6]) # CSVに書き込むデータのストック場所
    # ---- コマンドをループさせる ----
    # この例では開口比ARを横軸、Ispを縦軸にとってPLOTする，Pcは複数条件振る
    for Pc in pc_array1:
        k = 0
        for AR in ar_array1:
            data = cea_fac(OF = 2, Pc = Pc, AR = AR, CR = 4) # 昔の人が見たら発狂しそうな記法 CRとO/Fは適当
            print data
            vsar_data_array[k] = np.array(data)
            k+=1
        g = 9.80665
        Isp = vsar_data_array[:,2] / g # 海面高度比推力 sec
        cf =  vsar_data_array[:,5]
        # ---- PLOT ----
        plt.plot(ar_array1, cf, label='Pc=%.1f' % (Pc))
        save_array = np.vstack([save_array, vsar_data_array])

    # ---- CSVで結果を保存 ----
    header = u'Pc[MPa], O/F[-], Isp_sea[sec], Isp_vac[sec], AR[-], cf[-]'
    np.savetxt(vsar_data_file, save_array, fmt='%.3f', delimiter=',', header = header)

    # ---- PLOTの設定 ----
    plt.xlim(1, 10)
    plt.xlabel('AR')
    plt.ylabel('Isp (sec)')
    plt.grid()
    plt.title('LOX/%s 100% frozen nfz=3' % (fuel))
    plt.legend(loc='best', fontsize=12)
    plt.savefig('ceatest_IspvsAR.png')
    plt.close()


    # ---- パラメータ指定 ----
    ar_array2 = np.linspace(2, 22, 5) # 適っ当にPc=1, 3, 5, 7MPa
    pc_array2 = np.linspace(0.5, 10, 100) # ARは適っ当に2から10までを50分割してみる
    vspc_data_array = np.zeros((len(pc_array2), 6))
    save_array = np.zeros([1,6]) # CSVに書き込むデータのストック場所
    # ---- コマンドをループさせる ----
    # この例では開口比ARを横軸、Ispを縦軸にとってPLOTする，Pcは複数条件振る
    for AR in ar_array2:
        k = 0
        for Pc in pc_array2:
            data = cea_fac(OF = 2, Pc = Pc, AR = AR, CR = 4) # 昔の人が見たら発狂しそうな記法 CRとO/Fは適当
            print data
            vspc_data_array[k] = np.array(data)
            k+=1
        g = 9.80665
        Isp = vspc_data_array[:,2] / g # 海面高度比推力 sec
        # ---- PLOT ----
        plt.plot(pc_array2, Isp, label='AR=%.1f' % (AR))
        save_array = np.vstack([save_array, vspc_data_array])

    # ---- CSVで結果を保存 ----
    header = u'Pc[MPa], O/F[-], Isp_sea[sec], Isp_vac[sec], AR[-], cf[-]'
    np.savetxt(vspc_data_file, save_array, fmt='%.3f', delimiter=',', header = header)

    # ---- PLOTの設定 ----
    plt.xlim(0.5, 10)
    plt.xlabel('Pc')
    plt.ylabel('Isp (sec)')
    plt.grid()
    plt.title('LOX/%s 100% frozen nfz=3' % (fuel))
    plt.legend(loc='best', fontsize=12)
    plt.savefig('ceatest_IspvsPc.png')
    plt.close()

    # ---- パラメータ指定 ----
    ar_array3 = np.linspace(3, 10, 15) # 適っ当にPc=1, 3, 5, 7MPa
    of_array3 = np.linspace(2.0, 2.5, 11) # ARは適っ当に2から10までを50分割してみる
    vsof_data_array = np.zeros((len(of_array3), 6))
    save_array = np.zeros([1,6]) # CSVに書き込むデータのストック場所
    # ---- コマンドをループさせる ----
    # この例では開口比ARを横軸、Ispを縦軸にとってPLOTする，Pcは複数条件振る
    for AR in ar_array3:
        k = 0
        for OF in of_array3:
            data = cea_fac(OF = OF, Pc = 5.0, AR = AR, CR = 4) # 昔の人が見たら発狂しそうな記法 CRとO/Fは適当
            print data
            vsof_data_array[k] = np.array(data)
            k+=1
        g = 9.80665
        Isp = vsof_data_array[:,2] / g # 海面高度比推力 sec
        # ---- PLOT ----
        plt.plot(of_array3, Isp, label='AR=%1.f' % (AR))
        save_array = np.vstack([save_array, vsof_data_array])

    # ---- CSVで結果を保存 ----
    header = u'Pc[MPa], O/F[-], Isp_sea[sec], Isp_vac[sec], AR[-], cf[-]'
    np.savetxt(vsof_data_file, save_array, fmt='%.3f', delimiter=',', header = header)

    # ---- PLOTの設定 ----
    plt.xlim(1, 3)
    plt.xlabel('O/F')
    plt.ylabel('Isp (sec)')
    plt.grid()
    plt.title('LOX/%s 100% frozen nfz=3' % (fuel))
    plt.legend(loc='best', fontsize=12)
    plt.savefig('ceatest_IspvsOF.png')
    plt.close()



    # ---- パラメータ指定 ----
    ar_array4 = np.linspace(1.01, 8, 8) # 適っ当にPc=1, 3, 5, 7MPa
    pa_array4 = np.linspace(0, 0.101, 102) # ARは適っ当に2から10までを50分割してみる
    vspa_data_array = np.zeros((len(pa_array4), 6))
    save_array = np.zeros([1,6]) # CSVに書き込むデータのストック場所
    # ---- コマンドをループさせる ----
    # この例では開口比ARを横軸、Ispを縦軸にとってPLOTする，Pcは複数条件振る
    for AR in ar_array4:
        k = 0
        for pa in pa_array4:
            data = cea_fac(OF = 1.48, Pc = 1., AR = AR, CR = 4, pa = pa) # 昔の人が見たら発狂しそうな記法 CRとO/Fは適当
            print data
            vspa_data_array[k] = np.array(data)
            k+=1
        g = 9.80665
        Isp = vspa_data_array[:,2] / g # 海面高度比推力 sec
        cf =  vspa_data_array[:,5]
        # ---- PLOT ----
        plt.plot(pa_array4, cf, label='AR=%.1f' % (AR))
        save_array = np.vstack([save_array, vspa_data_array])

    # ---- CSVで結果を保存 ----
    header = u'Pc[MPa], O/F[-], Isp_sea[sec], Isp_vac[sec], AR[-], cf[-]'
    np.savetxt(vspa_data_file, save_array, fmt='%.3f', delimiter=',', header = header)

    # ---- PLOTの設定 ----
#    plt.xlim(1, 10)
    plt.xlabel('pa')
    plt.ylabel('cf (-)')
    plt.grid()
    plt.title('LOX/%s 100% frozen nfz=3' % (fuel))
    plt.legend(loc='best', fontsize=12)
    plt.savefig('ceatest_Ispvspa.png')
    plt.close()

