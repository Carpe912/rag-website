#!/usr/bin/env python3
"""
测试父子 Chunk 策略
"""

import sys
sys.path.insert(0, '.')

from rag import _split_into_parent_child_chunks

# 测试文本（约 3000 字）
test_text = """
# 人工智能技术概述

人工智能（Artificial Intelligence，简称AI）是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。该领域的研究包括机器人、语言识别、图像识别、自然语言处理和专家系统等。

## 机器学习基础

机器学习是人工智能的核心，是使计算机具有智能的根本途径。机器学习的应用已经遍及人工智能的各个分支，如专家系统、自动推理、自然语言理解、模式识别、计算机视觉、智能机器人等领域。

### 监督学习

监督学习是机器学习中最常见的一种学习方式。在监督学习中，我们有一个数据集，这个数据集包含了输入和期望的输出。算法的目标是学习一个函数，这个函数能够将输入映射到输出。常见的监督学习算法包括线性回归、逻辑回归、支持向量机、决策树、随机森林和神经网络等。

线性回归是最简单的监督学习算法之一。它假设输入和输出之间存在线性关系，并试图找到最佳拟合直线。逻辑回归虽然名字中有"回归"，但实际上是一种分类算法，常用于二分类问题。

支持向量机（SVM）是一种强大的分类算法，它通过找到最优的超平面来分隔不同类别的数据点。决策树是一种树形结构的分类器，它通过一系列的判断来对数据进行分类。随机森林是决策树的集成方法，通过构建多个决策树并综合它们的预测结果来提高准确性。

### 无监督学习

无监督学习是另一种重要的机器学习方式。与监督学习不同，无监督学习的数据集中只有输入，没有对应的输出标签。算法的目标是从数据中发现隐藏的模式或结构。常见的无监督学习算法包括聚类、降维和异常检测等。

聚类是无监督学习中最常见的任务之一。K-means是最流行的聚类算法，它将数据点分成K个簇，使得每个数据点都属于离它最近的簇中心所代表的簇。层次聚类是另一种聚类方法，它通过构建一个树形结构来表示数据的层次关系。

降维是另一个重要的无监督学习任务。主成分分析（PCA）是最常用的降维方法，它通过线性变换将高维数据投影到低维空间，同时保留数据的主要特征。t-SNE是另一种流行的降维方法，特别适合用于数据可视化。

### 强化学习

强化学习是机器学习的第三大类。在强化学习中，智能体通过与环境的交互来学习最优策略。智能体在每个时间步选择一个动作，环境会给出一个奖励和新的状态。智能体的目标是学习一个策略，使得长期累积奖励最大化。

Q-learning是最经典的强化学习算法之一。它通过学习一个Q函数来评估在某个状态下采取某个动作的价值。深度Q网络（DQN）将深度学习与Q-learning结合，使得强化学习能够处理高维状态空间。

策略梯度方法是另一类重要的强化学习算法。与Q-learning不同，策略梯度方法直接学习策略函数，而不是价值函数。Actor-Critic方法结合了价值函数和策略函数的优点，是目前最先进的强化学习方法之一。

## 深度学习

深度学习是机器学习的一个分支，它使用多层神经网络来学习数据的表示。深度学习在图像识别、语音识别、自然语言处理等领域取得了突破性的进展。

### 卷积神经网络

卷积神经网络（CNN）是深度学习中最重要的模型之一，特别适合处理图像数据。CNN通过卷积层、池化层和全连接层的组合来提取图像特征。卷积层使用卷积核在图像上滑动，提取局部特征。池化层用于降低特征图的维度，减少计算量。

经典的CNN架构包括LeNet、AlexNet、VGG、GoogLeNet和ResNet等。ResNet引入了残差连接，解决了深层网络的梯度消失问题，使得训练非常深的网络成为可能。

### 循环神经网络

循环神经网络（RNN）是处理序列数据的重要模型。RNN通过在时间步之间传递隐藏状态来捕捉序列中的时间依赖关系。然而，传统的RNN存在梯度消失和梯度爆炸的问题，难以学习长期依赖。

长短期记忆网络（LSTM）和门控循环单元（GRU）是RNN的改进版本，它们通过引入门控机制来解决长期依赖问题。LSTM使用输入门、遗忘门和输出门来控制信息的流动，而GRU则简化了LSTM的结构，使用更新门和重置门。

### Transformer架构

Transformer是近年来最重要的深度学习架构之一。它完全基于注意力机制，不使用循环或卷积结构。Transformer在自然语言处理领域取得了巨大成功，BERT、GPT等模型都是基于Transformer架构。

自注意力机制是Transformer的核心。它允许模型在处理序列中的每个位置时，关注序列中的所有位置。多头注意力机制进一步增强了模型的表达能力，允许模型从不同的表示子空间中学习信息。

位置编码是Transformer的另一个重要组成部分。由于Transformer不使用循环结构，它需要通过位置编码来注入序列的位置信息。常用的位置编码方法包括正弦位置编码和可学习的位置编码。

## 自然语言处理

自然语言处理（NLP）是人工智能的一个重要分支，它研究如何让计算机理解和生成人类语言。NLP的应用包括机器翻译、文本分类、情感分析、问答系统等。

预训练语言模型是近年来NLP领域的重大突破。BERT通过在大规模语料上进行预训练，学习了丰富的语言表示。GPT系列模型则展示了大规模语言模型的强大能力，能够完成各种语言任务。

## 计算机视觉

计算机视觉是让计算机能够"看"的技术。它包括图像分类、目标检测、图像分割、人脸识别等任务。深度学习的发展极大地推动了计算机视觉的进步。

目标检测是计算机视觉中的重要任务。YOLO、Faster R-CNN等算法能够实时检测图像中的多个目标。图像分割则更进一步，不仅要检测目标，还要精确地分割出目标的轮廓。

## 未来展望

人工智能技术正在快速发展，未来将在更多领域发挥重要作用。通用人工智能（AGI）是人工智能研究的终极目标，它指的是能够像人类一样理解、学习和应用知识的人工智能系统。虽然我们距离实现AGI还有很长的路要走，但每一步进展都让我们离这个目标更近一步。
""" * 2  # 重复一次，确保文本足够长

def test_parent_child_chunks():
    print("=" * 80)
    print("测试父子 Chunk 策略")
    print("=" * 80)

    # 测试父子分块
    chunks = _split_into_parent_child_chunks(test_text)

    print(f"\n总文本长度: {len(test_text)} 字符")
    print(f"生成的块数: {len(chunks)}")

    # 统计父块和子块
    parent_chunks = [c for c in chunks if c[2] is None]
    child_chunks = [c for c in chunks if c[2] is not None]

    print(f"父块数量: {len(parent_chunks)}")
    print(f"子块数量: {len(child_chunks)}")

    # 显示前几个块的信息
    print("\n" + "=" * 80)
    print("前 5 个块的详细信息:")
    print("=" * 80)

    for i, (text, start, parent_id) in enumerate(chunks[:5]):
        chunk_type = "父块" if parent_id is None else f"子块 (父块: {parent_id})"
        print(f"\n块 {i + 1} [{chunk_type}]:")
        print(f"  起始位置: {start}")
        print(f"  长度: {len(text)} 字符")
        print(f"  内容预览: {text[:100]}...")

    # 验证父子关系
    print("\n" + "=" * 80)
    print("验证父子关系:")
    print("=" * 80)

    # 重新构建父子关系映射
    parent_map = {}

    # 第一遍：找出所有父块
    for i, (text, start, parent_id) in enumerate(chunks):
        if parent_id is None:
            # 这是父块，使用索引作为临时 ID
            temp_id = f"parent_{len(parent_map)}"
            parent_map[temp_id] = {
                "index": i,
                "length": len(text),
                "children": [],
                "temp_id": temp_id
            }

    # 第二遍：找出所有子块并关联到父块
    for i, (text, start, parent_id) in enumerate(chunks):
        if parent_id is not None:
            # 这是子块
            if parent_id in parent_map:
                parent_map[parent_id]["children"].append(i)

    # 显示前3个有子块的父块信息
    displayed = 0
    for parent_id, info in parent_map.items():
        if displayed >= 3:
            break
        if info['children']:  # 只显示有子块的父块
            print(f"\n{parent_id}:")
            print(f"  索引: {info['index']}")
            print(f"  长度: {info['length']} 字符")
            print(f"  子块数量: {len(info['children'])}")
            print(f"  子块索引: {info['children'][:5]}{'...' if len(info['children']) > 5 else ''}")

            # 显示第一个子块的信息
            if info['children']:
                first_child_idx = info['children'][0]
                child_text, child_start, child_parent_id = chunks[first_child_idx]
                print(f"  第一个子块预览: {child_text[:80]}...")

            displayed += 1

    # 统计信息
    total_parents_with_children = sum(1 for info in parent_map.values() if info['children'])
    total_children = sum(len(info['children']) for info in parent_map.values())

    print(f"\n统计:")
    print(f"  有子块的父块数量: {total_parents_with_children}/{len(parent_map)}")
    print(f"  子块总数: {total_children}")
    print(f"  平均每个父块的子块数: {total_children / len(parent_map):.1f}")

    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)

if __name__ == "__main__":
    test_parent_child_chunks()
