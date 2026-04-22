"""
SQL 表名重写器 - 将业务表名替换为影子表名

支持 SELECT/INSERT/UPDATE/DELETE/JOIN/CREATE 等语句。
基于 business_shadow_tables 映射或自动 PT_ 前缀。
"""

import logging
import re
from typing import Dict, Set

logger = logging.getLogger(__name__)


class ShadowSQLRewriter:
    """
    SQL 重写器

    将 SQL 中的业务表名替换为影子表名。
    """

    # SQL 关键字，后面跟表名
    TABLE_KEYWORDS = {
        'FROM', 'INTO', 'UPDATE', 'JOIN', 'INNER JOIN', 'LEFT JOIN',
        'RIGHT JOIN', 'FULL JOIN', 'CROSS JOIN', 'NATURAL JOIN',
        'TABLE', 'TRUNCATE', 'DESCRIBE', 'DESC', 'EXPLAIN',
    }

    # 子句后可能跟表名
    SUBCLAUSE_KEYWORDS = {
        'WHERE', 'AND', 'OR', 'ON', 'SET', 'ORDER BY', 'GROUP BY',
        'HAVING', 'LIMIT', 'UNION', 'UNION ALL', 'INTERSECT', 'EXCEPT',
    }

    def __init__(self, table_mapping: Dict[str, str]):
        """
        Args:
            table_mapping: {原始表名: 影子表名} 映射
        """
        self._mapping = {k.lower(): v for k, v in table_mapping.items()}
        self._tables = set(self._mapping.keys())

    def rewrite(self, sql: str) -> str:
        """
        重写 SQL 中的表名

        Args:
            sql: 原始 SQL 语句

        Returns:
            重写后的 SQL
        """
        if not sql or not self._mapping:
            return sql

        # 使用正则匹配表名
        # 匹配模式: 关键字 空格/换行 表名
        result = []
        tokens = self._tokenize(sql)

        i = 0
        while i < len(tokens):
            token = tokens[i]

            # 检查是否是关键字
            if token.upper().strip() in self.TABLE_KEYWORDS:
                result.append(token)
                # 跳过空白
                if i + 1 < len(tokens) and tokens[i + 1].strip() == '':
                    i += 1
                    result.append(tokens[i])
                # 检查下一个 token 是否是表名
                if i + 1 < len(tokens):
                    next_token = tokens[i + 1]
                    table_name = next_token.strip().strip('`').strip('"').strip("'")
                    if table_name.lower() in self._mapping:
                        shadow_name = self._mapping[table_name.lower()]
                        # 保留引号风格
                        if next_token.startswith('`'):
                            result.append(f'`{shadow_name}`')
                        elif next_token.startswith('"'):
                            result.append(f'"{shadow_name}"')
                        elif next_token.startswith("'"):
                            result.append(f"'{shadow_name}'")
                        else:
                            result.append(shadow_name)
                        i += 1
                    else:
                        result.append(next_token)
                        i += 1
                i += 1
                continue

            # 检查 UPDATE table SET 模式
            if token.upper().strip() == 'UPDATE':
                result.append(token)
                if i + 1 < len(tokens):
                    # 跳过空白
                    if tokens[i + 1].strip() == '':
                        i += 1
                        result.append(tokens[i])
                    next_token = tokens[i + 1] if i + 1 < len(tokens) else ''
                    table_name = next_token.strip().strip('`').strip('"').strip("'")
                    if table_name.lower() in self._mapping:
                        shadow_name = self._mapping[table_name.lower()]
                        result.append(self._preserve_quotes(next_token, shadow_name))
                        i += 1
                    else:
                        result.append(next_token)
                        i += 1
                i += 1
                continue

            result.append(token)
            i += 1

        return ''.join(result)

    def rewrite_table(self, table_name: str) -> str:
        """
        重写单个表名

        Args:
            table_name: 原始表名

        Returns:
            影子表名或原表名
        """
        return self._mapping.get(table_name.lower(), table_name)

    def needs_rewrite(self, sql: str) -> bool:
        """检查 SQL 是否需要重写"""
        sql_lower = sql.lower()
        for table in self._tables:
            # 检查表名是否在 SQL 中出现
            pattern = r'\b' + re.escape(table) + r'\b'
            if re.search(pattern, sql_lower):
                return True
        return False

    def get_mapping(self) -> Dict[str, str]:
        """获取表名映射"""
        return dict(self._mapping)

    # ==================== 内部方法 ====================

    @staticmethod
    def _tokenize(sql: str) -> list:
        """将 SQL 分词 (保留空白和符号)"""
        # 按关键字和表名边界分割
        tokens = []
        current = ''
        i = 0
        while i < len(sql):
            ch = sql[i]
            if ch in (' ', '\t', '\n', '\r'):
                if current:
                    tokens.append(current)
                    current = ''
                tokens.append(ch)
            elif ch in ('(', ')', ',', ';', '=', '<', '>', '!', '+', '-', '*', '/'):
                if current:
                    tokens.append(current)
                    current = ''
                tokens.append(ch)
            else:
                current += ch
            i += 1
        if current:
            tokens.append(current)
        return tokens

    @staticmethod
    def _preserve_quotes(original: str, new_name: str) -> str:
        """保留原始表名的引号样式"""
        stripped = original.strip()
        if stripped.startswith('`'):
            return f'`{new_name}`'
        elif stripped.startswith('"'):
            return f'"{new_name}"'
        return new_name


class AutoPrefixRewriter(ShadowSQLRewriter):
    """
    自动前缀重写器

    不依赖映射表, 自动为所有表名添加 PT_ 前缀。
    """

    def __init__(self, prefix: str = "PT_"):
        self.prefix = prefix
        super().__init__({})

    def rewrite(self, sql: str) -> str:
        """自动为 SQL 中的表名加前缀"""
        if not sql:
            return sql

        # 简单的表名匹配: 在 FROM/JOIN/UPDATE/INTO 后面的标识符
        def _replace(match):
            prefix_word = match.group(1)  # FROM/JOIN/...
            table = match.group(2)  # 表名
            # 如果是 SQL 关键字则跳过
            if table.upper() in self.TABLE_KEYWORDS | self.SUBCLAUSE_KEYWORDS:
                return match.group(0)
            return f"{prefix_word}{self.prefix}{table}"

        # 匹配 FROM/JOIN/UPDATE/INTO 后面的表名
        pattern = r'((?:FROM|JOIN|INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+JOIN|UPDATE|INTO)\s+)(\S+)'
        result = re.sub(pattern, _replace, sql, flags=re.IGNORECASE)
        return result
